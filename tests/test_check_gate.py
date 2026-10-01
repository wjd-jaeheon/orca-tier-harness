"""Black-box gate checks using real, disposable evidence and CLI processes."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-gate.py"
MISSING = object()


class CheckGateTests(unittest.TestCase):
    def artifacts(self):
        temporary = tempfile.TemporaryDirectory(prefix="check-gate-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / "attempt"
        self.root.mkdir()
        (self.root / "logs").mkdir()
        self.contract_path = self.root / "contract.json"
        self.result_path = self.root / "result.json"
        self.contract = {
            "schema_version": 1, "attempt_id": "attempt-01",
            "base_sha": "a" * 40, "candidate_sha": "b" * 40,
            "member_shas": ["c" * 40, "d" * 64],
            "required_environment": ["postgres", "browser"],
            "stages": [
                {"id": "unit", "required_tests": ["unit::required"]},
                {"id": "integration", "required_tests": ["db::required"]},
            ],
        }
        self.result = {
            key: copy.deepcopy(self.contract[key]) for key in
            ("schema_version", "attempt_id", "base_sha", "candidate_sha", "member_shas")
        }
        self.result.update({
            "completed": True, "head_start": "b" * 40, "head_end": "b" * 40,
            "clean_start": True, "clean_end": True,
            "environment": {"postgres": True, "browser": True},
            "stages": [],
        })
        for stage, test_id in (("unit", "unit::required"), ("integration", "db::required")):
            log = b"passed\r\n\x00\xff\n"  # Hash bytes, not decoded/normalized text.
            (self.root / "logs" / (stage + ".log")).write_bytes(log)
            self.result["stages"].append({
                "id": stage, "completed": True, "exit_code": 0,
                "tests": [{"id": test_id, "status": "passed"}],
                "log_path": "logs/" + stage + ".log",
                "log_sha256": hashlib.sha256(log).hexdigest(),
            })
        self.result["stages"][0]["tests"] += [
            {"id": "optional::pass", "status": "passed"},
            {"id": "optional::skip", "status": "skipped"},
        ]
        (self.directory / "outside.log").write_bytes(log)

    def freeze(self):
        self.contract_path.write_bytes(json.dumps(self.contract, indent=2).encode("utf-8"))
        self.digest = hashlib.sha256(self.contract_path.read_bytes()).hexdigest()
        self.result["contract_sha256"] = self.digest
        self.write_result()

    def write_result(self):
        self.result_path.write_bytes(json.dumps(self.result).encode("utf-8"))

    def invoke(self, success=False, args=None):
        def snapshot():
            return {str(p.relative_to(self.directory)): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in self.directory.rglob("*") if p.is_file()}

        before = snapshot()
        if args is None:
            args = [str(self.contract_path), str(self.result_path),
                    "--contract-sha256", self.digest]
        process = subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                                 cwd=self.directory, capture_output=True, text=True, timeout=10)
        self.assertEqual(snapshot(), before, "validator changed its inputs")
        self.assertEqual(process.stderr, "", process.stderr)
        self.assertEqual(len(process.stdout.splitlines()), 1, process.stdout)
        output = json.loads(process.stdout)
        self.assertIn(output["status"], ("passed", "failed", "unverified"))
        if success:
            self.assertEqual(process.returncode, 0, output)
            self.assertEqual(output["status"], "passed")
        else:
            self.assertNotEqual(process.returncode, 0, output)
            self.assertNotEqual(output["status"], "passed")
            self.assertTrue(output["reasons"], output)
        return output

    def bad_variants(self, document, variants):
        for path, value in variants:
            with self.subTest(document=document, path=path, value=value):
                self.artifacts()
                self.freeze()
                target = self.contract if document == "contract" else self.result
                for key in path[:-1]:
                    target = target[key]
                if value is MISSING:
                    del target[path[-1]]
                else:
                    target[path[-1]] = value
                if document == "contract":
                    # Matching bad identities must fail schema validation, not just comparison.
                    for key in ("attempt_id", "base_sha", "candidate_sha", "member_shas"):
                        if key in self.contract:
                            self.result[key] = copy.deepcopy(self.contract[key])
                    self.result["head_start"] = self.result["head_end"] = self.contract.get("candidate_sha")
                    self.freeze()
                else:
                    self.write_result()
                self.invoke()

    def test_valid_cli_counts_optional_skips_and_ignores_status_claim(self):
        self.artifacts()
        self.result["status"] = "failed"
        self.result["command"] = "must never execute"
        self.result["stages"].reverse()  # Stage order is not identity.
        self.result["environment"]["optional_service"] = False
        self.freeze()
        output = self.invoke(success=True)
        self.assertEqual(output["counters"]["stages"], 2)
        self.assertEqual(output["counters"]["tests"], 4)
        self.assertEqual(output["counters"]["passed"], 3)
        self.assertEqual(output["counters"]["skipped"], 1)
        self.assertEqual(output["counters"]["required_tests"], 2)

    def test_build_only_accepts_empty_tests_environment_and_log(self):
        self.artifacts()
        self.contract["required_environment"] = []
        self.result["environment"] = {}
        for stage in self.contract["stages"]:
            stage["required_tests"] = []
        for stage in self.result["stages"]:
            stage["tests"] = []
            (self.root / stage["log_path"]).write_bytes(b"")
            stage["log_sha256"] = hashlib.sha256(b"").hexdigest()
        self.freeze()
        output = self.invoke(success=True)
        self.assertEqual(output["counters"]["tests"], 0)

    def test_large_binary_log_hash_includes_final_partial_chunk(self):
        self.artifacts()
        log = bytes(range(256)) * 32768 + b"\x00final\xff\r\n"
        stage = self.result["stages"][0]
        (self.root / stage["log_path"]).write_bytes(log)
        stage["log_sha256"] = hashlib.sha256(log).hexdigest()
        self.freeze()
        self.invoke(success=True)

    def test_full_git_shas_and_test_ids_are_not_globally_restricted(self):
        self.artifacts()
        for key in ("base_sha", "candidate_sha"):
            self.contract[key] = "ABCDEF01" * 8
            self.result[key] = self.contract[key]
        self.result["head_start"] = self.result["head_end"] = self.contract["candidate_sha"]
        self.contract["stages"][1]["required_tests"] = ["unit::required"]
        self.result["stages"][1]["tests"][0]["id"] = "unit::required"
        self.freeze()
        self.invoke(success=True)

    def test_contract_schema_rejects_missing_malformed_and_duplicate_fields(self):
        self.artifacts()
        variants = [((key,), MISSING) for key in self.contract]
        bad = {
            "schema_version": [True, False, 1.0, "1", 2, None],
            "attempt_id": ["", " \t", None, 1, [], {}],
            "base_sha": ["a" * 39, "g" * 40, "a" * 41, None, 1, []],
            "candidate_sha": ["b" * 63, "b" * 65, "b" * 40 + "\n", False],
            "member_shas": [[], "c" * 40, {}, None, ["c" * 40] * 2, [True], [[]], ["short"]],
            "required_environment": [None, "postgres", {}, ["postgres"] * 2, [""], [" "], [1], [[]]],
            "stages": [[], None, {}, "unit", [None], [[]]],
        }
        variants += [((key,), value) for key, values in bad.items() for value in values]
        variants += [(("stages", 0, key), value) for key, values in {
            "id": [MISSING, None, "", " ", 1, []],
            "required_tests": [MISSING, None, "test", {}, [""], [" "], [1], [[]], ["same"] * 2],
        }.items() for value in values]
        variants.append((("stages", 1, "id"), "unit"))
        self.bad_variants("contract", variants)

    def test_result_rejects_partial_stale_dirty_and_malformed_evidence(self):
        self.artifacts()
        self.freeze()
        variants = [((key,), MISSING) for key in self.result]
        bad = {
            "schema_version": [True, 1.0, "1", 2, None],
            "attempt_id": ["stale", "", None, 1, []],
            "base_sha": ["e" * 40, "short", None, []],
            "candidate_sha": ["e" * 40, "b" * 64, False],
            "member_shas": [[], "c" * 40, None, ["c" * 40] * 2,
                            ["d" * 64, "c" * 40], ["c" * 40], [[]]],
            "contract_sha256": ["0" * 64, "A" * 64, "x" * 64, None, True],
            "completed": [False, 1, "true", None, []],
            "head_start": ["e" * 40, None, True],
            "head_end": ["e" * 40, None, True],
            "clean_start": [False, 1, "true", None],
            "clean_end": [False, 1, "true", None],
            "environment": [None, [], True, {}],
            "stages": [[], None, {}, "unit", [None], [[]]],
        }
        variants += [((key,), value) for key, values in bad.items() for value in values]
        variants += [(("environment", "postgres"), v) for v in
                     (MISSING, False, 1, "true", None, [], {"secret": "private-token"})]
        variants += [(("environment", "extra"), "private-token")]
        variants += [(("stages", 0, key), value) for key, values in {
            "id": [MISSING, "unknown", "", 1, [], None],
            "completed": [MISSING, False, 1, "true", None],
            "exit_code": [MISSING, True, False, 0.0, "0", None, []],
            "tests": [MISSING, None, {}, "test", [None], [[]]],
            "log_path": [MISSING, None, "", 1, []],
            "log_sha256": [MISSING, None, True, [], "", "A" * 64, "0" * 64],
        }.items() for value in values]
        variants += [(("stages", 1, "id"), "unit")]
        variants += [(("stages", 0, "tests", 0, key), value) for key, values in {
            "id": [MISSING, None, "", " ", 1, []],
            "status": [MISSING, None, True, [], {}, "PASSED", "unknown"],
        }.items() for value in values]
        self.bad_variants("result", variants)

    def test_missing_extra_stages_and_duplicate_tests_fail(self):
        for change in ("missing-stage", "extra-stage", "duplicate-stage", "duplicate-test",
                       "missing-test", "wrong-stage", "unregistered-test"):
            with self.subTest(change=change):
                self.artifacts()
                stages = self.result["stages"]
                if change == "missing-stage":
                    stages.pop()
                elif change in ("extra-stage", "duplicate-stage"):
                    stages.append(copy.deepcopy(stages[0]))
                    if change == "extra-stage":
                        stages[-1]["id"] = "extra"
                elif change == "duplicate-test":
                    stages[0]["tests"].append(copy.deepcopy(stages[0]["tests"][0]))
                elif change == "missing-test":
                    stages[0]["tests"] = []
                elif change == "wrong-stage":
                    stages[1]["tests"].append(stages[0]["tests"].pop(0))
                else:
                    stages[0]["tests"][0]["id"] = "different-test"
                self.freeze()
                self.invoke()

    def test_reported_failures_and_required_skips_cannot_be_overridden(self):
        cases = [("exit", 1), ("exit", -1)]
        cases += [(kind, status) for kind in ("required", "optional")
                  for status in ("failed", "cancelled", "skipped") if
                  (kind, status) != ("optional", "skipped")]
        for kind, status in cases:
            with self.subTest(kind=kind, status=status):
                self.artifacts()
                self.result["status"] = "passed"
                if kind == "exit":
                    self.result["stages"][0]["exit_code"] = status
                else:
                    index = 0 if kind == "required" else 1
                    self.result["stages"][0]["tests"][index]["status"] = status
                self.freeze()
                output = self.invoke()
                self.assertEqual(output["status"], "failed")

    def test_json_errors_duplicate_keys_and_non_objects_fail_closed(self):
        for which in ("contract", "result"):
            for raw in (b"", b'{"schema_version":', b"{} {}", b"[]", b"null", b"true",
                        b"42", b'"text"', b"\xff", b'{"extra": NaN}', b'{"extra": Infinity}',
                        b'{"extra": -Infinity}', b"[" * 2000):
                with self.subTest(which=which, raw=raw[:40]):
                    self.artifacts()
                    self.freeze()
                    path = self.contract_path if which == "contract" else self.result_path
                    path.write_bytes(raw)
                    if which == "contract":
                        self.digest = hashlib.sha256(raw).hexdigest()
                        self.result["contract_sha256"] = self.digest
                        self.write_result()
                    self.invoke()
            for duplicate in ('"schema_version":1,', '"extra":{"x":1,"x":1},'):
                with self.subTest(which=which, duplicate=duplicate):
                    self.artifacts()
                    self.freeze()
                    path = self.contract_path if which == "contract" else self.result_path
                    raw = b"{" + duplicate.encode() + path.read_bytes()[1:]
                    path.write_bytes(raw)
                    if which == "contract":
                        self.digest = hashlib.sha256(raw).hexdigest()
                        self.result["contract_sha256"] = self.digest
                        self.write_result()
                    self.invoke()

    def test_file_errors_mutation_and_attempt_directory_confinement(self):
        for change in ("missing-contract", "missing-result", "missing-log", "contract-directory",
                       "result-directory", "log-directory", "mutated-contract", "mutated-log",
                       "sibling-result", "nested-result"):
            with self.subTest(change=change):
                self.artifacts()
                self.freeze()
                paths = {"contract": self.contract_path, "result": self.result_path,
                         "log": self.root / "logs/unit.log"}
                if change.startswith("missing-"):
                    paths[change[8:]].unlink()
                elif change.endswith("-directory"):
                    path = paths[change[:-10]]
                    path.unlink()
                    path.mkdir()
                elif change.startswith("mutated-"):
                    path = paths[change[8:]]
                    path.write_bytes(path.read_bytes() + b" ")
                else:
                    destination = self.directory if change == "sibling-result" else self.root / "logs"
                    self.result_path = self.result_path.rename(destination / "result.json")
                self.invoke()

    def test_log_paths_reject_traversal_absolute_drives_and_streams(self):
        self.artifacts()
        paths = ["../outside.log", "..\\outside.log", "logs/../../outside.log",
                 "logs/../logs/unit.log", "logs\\..\\logs\\unit.log",
                 "/outside.log", "\\outside.log", "C:/outside.log", "C:outside.log",
                 "//server/share/log", "\\\\server\\share\\log", "logs/unit.log:stream",
                 "logs/unit.log\x00", str(self.root / "logs/unit.log")]
        self.bad_variants("result", [(("stages", 0, "log_path"), path) for path in paths])

    def test_resolved_symlinks_stay_inside_attempt(self):
        self.artifacts()
        link = self.root / "linked.log"
        try:
            link.symlink_to(self.root / "logs/unit.log")
        except (OSError, NotImplementedError) as error:
            self.skipTest("symlinks unavailable: " + str(error))
        self.result["stages"][0]["log_path"] = "linked.log"
        self.freeze()
        self.invoke(success=True)
        link.unlink()
        link.symlink_to(self.directory / "outside.log")
        self.invoke()
        link.unlink()
        directory_link = self.root / "linked-directory"
        directory_link.symlink_to(self.directory, target_is_directory=True)
        self.result["stages"][0]["log_path"] = "linked-directory/outside.log"
        self.write_result()
        self.invoke()
        directory_link.unlink()
        self.result["stages"][0]["log_path"] = "logs/unit.log"
        self.write_result()
        external_result = self.result_path.rename(self.directory / "external-result.json")
        self.result_path.symlink_to(external_result)
        self.invoke()

    def test_cli_digest_and_arguments_fail_as_json(self):
        self.artifacts()
        self.freeze()
        prefix = [str(self.contract_path), str(self.result_path)]
        for digest in ("", "a" * 63, "a" * 65, "g" * 64, "A" * 64,
                       "0" * 64, self.digest + "\n"):
            with self.subTest(digest=digest):
                self.invoke(args=[*prefix, "--contract-sha256", digest])
        for args in ([], prefix, [*prefix, "--wrong", self.digest],
                     [*prefix, "--contract-sha256", self.digest, "extra"]):
            with self.subTest(args=args):
                self.invoke(args=args)

    def test_secret_environment_value_is_rejected_without_echoing_it(self):
        self.artifacts()
        self.result["environment"]["postgres"] = "private-token-do-not-print"
        self.freeze()
        output = self.invoke()
        self.assertNotIn("private-token-do-not-print", json.dumps(output))


if __name__ == "__main__":
    unittest.main()
