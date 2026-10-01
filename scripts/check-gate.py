#!/usr/bin/env python3
"""Validate frozen v1 gate evidence; never execute commands or modify inputs.

Usage: python scripts/check-gate.py CONTRACT RESULT --contract-sha256 SHA256
Exit 0: passed; 1: reported failure; 2: unverified evidence (including bad CLI).
JSON is UTF-8 with unique keys. Extra metadata is ignored, including status.
IDs are nonblank strings, unique within each list/stage; member order is exact.
Git SHAs accept either hex case (identity is exact); SHA256 digests are lowercase.
Paths may contain subdirectories but no parent traversal, drives or streams.
Evidence is checked at read time; this does not authenticate the producer or
provide locking against concurrent writers.
"""
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def identifier(value):
    return isinstance(value, str) and bool(value.strip())


def matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("non_json_constant")


def parse(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def read_file(path):
    require(path.is_file(), "missing_or_non_regular_file")
    return path.read_bytes()


def unique_strings(value, label):
    require(isinstance(value, list), label + "_must_be_list")
    require(all(identifier(item) for item in value), label + "_invalid_identifier")
    require(len(set(value)) == len(value), label + "_duplicate")
    return value


def records(value, label):
    require(isinstance(value, list), label + "_must_be_list")
    result = {}
    for item in value:
        require(isinstance(item, dict), label + "_invalid_record")
        key = item.get("id")
        require(identifier(key), label + "_invalid_id")
        require(key not in result, label + "_duplicate_id")
        result[key] = item
    return result


def validate(contract_path, result_path, digest):
    require(matches(digest, r"[0-9a-f]{64}"), "invalid_contract_sha256")
    contract_path = contract_path.resolve(strict=True)
    root = contract_path.parent
    require(result_path.parent.resolve(strict=True) == root, "result_outside_attempt")
    result_path = result_path.resolve(strict=True)
    require(result_path.parent == root, "result_outside_attempt")
    raw = read_file(contract_path)
    require(hashlib.sha256(raw).hexdigest() == digest, "contract_sha256_mismatch")
    contract, result = parse(raw), parse(read_file(result_path))
    for document in (contract, result):
        require(isinstance(document, dict), "document_must_be_object")
        version = document.get("schema_version")
        require(type(version) is int and version == 1, "invalid_schema_version")

    require(identifier(contract.get("attempt_id")), "invalid_attempt_id")
    for key in ("base_sha", "candidate_sha"):
        require(matches(contract.get(key), r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})"),
                "invalid_" + key)
    members = unique_strings(contract.get("member_shas"), "member_shas")
    require(bool(members) and all(matches(sha, r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})")
                                  for sha in members), "invalid_member_shas")
    required_environment = unique_strings(contract.get("required_environment"),
                                          "required_environment")
    declared = records(contract.get("stages"), "contract_stages")
    require(bool(declared), "contract_stages_empty")
    required = {key: unique_strings(stage.get("required_tests"), "required_tests")
                for key, stage in declared.items()}

    for key in ("attempt_id", "base_sha", "candidate_sha", "member_shas"):
        require(result.get(key) == contract[key], key + "_mismatch")
    require(result.get("contract_sha256") == digest, "result_contract_sha256_mismatch")
    for key in ("completed", "clean_start", "clean_end"):
        require(result.get(key) is True, key + "_not_true")
    for key in ("head_start", "head_end"):
        require(result.get(key) == contract["candidate_sha"], key + "_mismatch")
    environment = result.get("environment")
    require(isinstance(environment, dict), "environment_must_be_object")
    require(all(identifier(key) and type(value) is bool for key, value in environment.items()),
            "environment_must_contain_boolean_identities")
    require(all(environment.get(key) is True for key in required_environment),
            "required_environment_not_true")
    emitted = records(result.get("stages"), "result_stages")
    require(emitted.keys() == declared.keys(), "stage_set_mismatch")

    counters = {"stages": len(emitted), "required_tests": sum(map(len, required.values())),
                "tests": 0, "passed": 0, "failed": 0, "skipped": 0, "cancelled": 0}
    failures = set()
    for key, stage in emitted.items():
        require(stage.get("completed") is True, "stage_not_completed")
        exit_code = stage.get("exit_code")
        require(type(exit_code) is int, "exit_code_must_be_integer")
        if exit_code != 0:
            failures.add("nonzero_stage_exit")
        tests = records(stage.get("tests"), "tests")
        for test in tests.values():
            status = test.get("status")
            require(isinstance(status, str) and status in ("passed", "failed", "skipped", "cancelled"),
                    "unknown_test_status")
            counters["tests"] += 1
            counters[status] += 1
            if status in ("failed", "cancelled"):
                failures.add("failed_or_cancelled_test")
        for test_id in required[key]:
            require(test_id in tests, "required_test_missing")
            if tests[test_id]["status"] != "passed":
                failures.add("required_test_not_passed")

        log_path = stage.get("log_path")
        require(identifier(log_path), "invalid_log_path")
        windows_path = PureWindowsPath(log_path)
        require(not windows_path.drive and not windows_path.root
                and ":" not in log_path and "\0" not in log_path
                and ".." not in log_path.replace("\\", "/").split("/"), "unsafe_log_path")
        log = (root / log_path).resolve(strict=True)
        require(log.is_relative_to(root), "log_outside_attempt")
        log_digest = stage.get("log_sha256")
        require(matches(log_digest, r"[0-9a-f]{64}"), "invalid_log_sha256")
        require(log.is_file(), "missing_or_non_regular_file")
        log_hash = hashlib.sha256()
        with log.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                log_hash.update(chunk)
        require(log_hash.hexdigest() == log_digest, "log_sha256_mismatch")

    return {"status": "failed" if failures else "passed", "reasons": sorted(failures),
            "counters": counters}


def main():
    try:
        args = sys.argv[1:]
        require(len(args) == 4 and args[2] == "--contract-sha256",
                "usage: check-gate.py CONTRACT RESULT --contract-sha256 SHA256")
        output = validate(Path(args[0]), Path(args[1]), args[3])
    except (json.JSONDecodeError, UnicodeError, RecursionError):
        output = {"status": "unverified", "reasons": ["invalid_json"]}
    except (OSError, RuntimeError):
        output = {"status": "unverified", "reasons": ["unreadable_evidence_or_path"]}
    except ValueError as error:
        output = {"status": "unverified", "reasons": [str(error)]}
    print(json.dumps(output, separators=(",", ":")))
    return {"passed": 0, "failed": 1, "unverified": 2}[output["status"]]


if __name__ == "__main__":
    sys.exit(main())
