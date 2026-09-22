#!/usr/bin/env python3
"""Deterministic checks on a dryforge 3-doc before tier-harness creates tasks.

usage: check-3doc.py [<repo root>]         exit 0 = OK, 1 = FAIL (reasons on stdout)
       check-3doc.py --hash [<repo root>]  print one sha256 over handoff+spec+plan

No third-party modules. The Execution Graph is parsed with a small parser that
accepts the shapes dryforge's ready writes (block list of tasks, flow or block
regen_barriers). If PyYAML is installed it is used instead.
"""
import hashlib
import os
import re
import sys

DOCS = ("handoff.md", "spec.md", "plan.md")
RISKS = (None, "", "RISKY", "MECHANICAL", "NONE")


def read(root, name):
    p = os.path.join(root, ".dryforge", name)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


def graph_block(plan):
    blocks = re.findall(r"^```ya?ml[^\n]*\n(.*?)^```", plan, re.S | re.M)
    blocks = [b for b in blocks if re.search(r"^\s*tasks\s*:", b, re.M)]
    if len(blocks) != 1:
        return None, "plan.md must contain exactly one ```yaml block with tasks:, found %d" % len(blocks)
    return blocks[0], None


def strip_comment(line):
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch == '"' or ch == "'":
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def parse_list(s):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    return [unquote(x) for x in s.split(",") if x.strip()]


def parse_graph(text):
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        tasks = [{"id": str(t.get("id")), "depends": [str(d) for d in (t.get("depends") or [])],
                  "risk": t.get("risk")} for t in (data.get("tasks") or [])]
        bars = [{"after": [str(a) for a in (b.get("after") or [])], "run": b.get("run")}
                for b in (data.get("regen_barriers") or [])]
        return tasks, bars
    except ImportError:
        pass
    tasks, bars, section, cur = [], [], None, None
    for raw in text.splitlines():
        line = strip_comment(raw)
        if not line.strip():
            continue
        if re.match(r"^tasks\s*:", line):
            section, cur = "tasks", None
            continue
        if re.match(r"^regen_barriers\s*:", line):
            section, cur = "bars", None
            rest = line.split(":", 1)[1].strip()
            if rest and rest != "[]":
                raise ValueError("regen_barriers inline value not supported: " + rest)
            continue
        m = re.match(r"^\s*-\s*(.*)$", line)
        if m:
            body = m.group(1).strip()
            if section == "tasks":
                cur = {"id": None, "depends": [], "risk": None}
                tasks.append(cur)
            elif section == "bars":
                cur = {"after": [], "run": None}
                bars.append(cur)
            else:
                raise ValueError("list item outside tasks/regen_barriers: " + line)
            if body.startswith("{"):
                for k, v in re.findall(r"(\w+)\s*:\s*(\[[^\]]*\]|\"[^\"]*\"|'[^']*'|[^,}]+)", body):
                    cur[k] = parse_list(v) if v.startswith("[") else unquote(v)
                continue
            line = body
        kv = re.match(r"^\s*(\w+)\s*:\s*(.*)$", line)
        if not kv or cur is None:
            raise ValueError("unrecognised line: " + raw)
        k, v = kv.group(1), kv.group(2).strip()
        if k in cur.setdefault("_seen", set()):
            raise ValueError("duplicate key %r in item %s" % (k, cur.get("id") or cur.get("after")))
        cur["_seen"].add(k)
        cur[k] = parse_list(v) if v.startswith("[") else unquote(v)
    for t in tasks:
        t["depends"] = t.get("depends") or []
    for b in bars:
        b["after"] = b.get("after") or []
    return tasks, bars


def find_cycle(ids, deps):
    color = {i: 0 for i in ids}
    stack = []

    def visit(n):
        color[n] = 1
        stack.append(n)
        for d in deps.get(n, []):
            if d not in color:
                continue
            if color[d] == 1:
                return stack[stack.index(d):] + [d]
            if color[d] == 0:
                c = visit(d)
                if c:
                    return c
        stack.pop()
        color[n] = 2
        return None

    for i in ids:
        if color[i] == 0:
            c = visit(i)
            if c:
                return c
    return None


def waves(ids, deps):
    order, done = [], set()
    while len(done) < len(ids):
        wave = [i for i in ids if i not in done and all(d in done for d in deps[i])]
        if not wave:
            break
        order.append(wave)
        done.update(wave)
    return order


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0] if args else ".")
    if "--hash" in sys.argv:
        h = hashlib.sha256()
        for name in DOCS:
            h.update((read(root, name) or "").encode("utf-8"))
            h.update(b"\0")
        print(h.hexdigest())
        return 0
    fails, warns = [], []
    docs = {n: read(root, n) for n in DOCS}
    for n, v in docs.items():
        if not v or not v.strip():
            fails.append("missing or empty .dryforge/" + n)
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    block, err = graph_block(docs["plan.md"])
    if err:
        print("FAIL")
        print(" -", err)
        return 1
    try:
        tasks, bars = parse_graph(block)
    except ValueError as e:
        print("FAIL")
        print(" - graph parse:", e)
        return 1
    ids = [t["id"] for t in tasks]
    if not ids:
        fails.append("graph has no tasks")
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        fails.append("duplicate task ids: " + ", ".join(dup))
    idset = set(ids)
    deps = {t["id"]: t["depends"] for t in tasks}
    risk = {t["id"]: (t.get("risk") or "-") for t in tasks}
    for t in tasks:
        for d in t["depends"]:
            if d not in idset:
                fails.append("%s depends on unknown task %s" % (t["id"], d))
        if t.get("risk") not in RISKS:
            fails.append("%s has invalid risk %r (RISKY | MECHANICAL | NONE)" % (t["id"], t["risk"]))
    for b in bars:
        for a in b["after"]:
            if a not in idset:
                fails.append("regen_barrier after unknown task " + a)
        if not b.get("run"):
            fails.append("regen_barrier without run command")
    cyc = find_cycle(ids, deps)
    if cyc:
        fails.append("dependency cycle: " + " -> ".join(cyc))
    body = re.sub(r"^```ya?ml[^\n]*\n.*?^```", "", docs["plan.md"], flags=re.S | re.M)
    heads = set(re.findall(r"^#{1,6}\s*\**([A-Za-z]+\d+)\b", body, re.M))
    if heads:
        if heads - idset:
            fails.append("tasks in plan body but not in graph: " + ", ".join(sorted(heads - idset)))
        if idset - heads:
            fails.append("tasks in graph but not in plan body: " + ", ".join(sorted(idset - heads)))
    else:
        warns.append("no task headings found in plan body; body/graph id agreement not checked")
    if not os.path.isfile(os.path.join(root, ".dryforge", "status.json")) and \
            not re.search(r"foundation", docs["handoff.md"], re.I):
        warns.append("first cycle (no status.json) but handoff.md has no Project Foundation section")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        for w in warns:
            print(" ?", w)
        return 1
    print("OK %d tasks, %d regen barriers" % (len(ids), len(bars)))
    for i, wave in enumerate(waves(ids, deps), 1):
        print(" wave %d: %s" % (i, ", ".join("%s(%s)" % (t, risk[t]) for t in wave)))
    for w in warns:
        print(" ?", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
