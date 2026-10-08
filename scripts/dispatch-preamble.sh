#!/bin/bash
# usage: dispatch-preamble.sh <terminal handle> <task_id> <tag> [receipt_dir]
# Dispatch path when `worker-start --terminal` fails (agent_readiness, terminal_worktree_mismatch):
#   task-update ready -> dispatch --task --to <handle> -> dispatch-show --preamble
#   -> save preamble file -> send one line -> confirm the line was submitted, not left as a draft.
# Run from the base checkout root. Receipts go to <receipt_dir> (default .harness/specs).
set -u
H=$1; T=$2; TAG=$3; R=${4:-.harness/specs}
ROOT=$(pwd -W 2>/dev/null || pwd)
export PYTHONIOENCODING=utf-8
mkdir -p "$R"
orca orchestration task-update --id "$T" --status ready --json > "$R/$TAG-ready.json" 2>&1
orca orchestration dispatch --task "$T" --to "$H" --json > "$R/$TAG-dispatch.json" 2>&1
C=$(grep -oE 'ctx_[0-9a-f]{12}' "$R/$TAG-dispatch.json" | head -1)
echo "dispatch=$C"
[ -z "$C" ] && { head -c 600 "$R/$TAG-dispatch.json"; exit 3; }
orca orchestration dispatch-show --task "$T" --preamble --json > "$R/$TAG-preamble.json" 2>&1
python - "$R" "$TAG" <<'PY'
import json,sys,io
r,tag=sys.argv[1],sys.argv[2]
d=json.load(io.open(f'{r}/{tag}-preamble.json',encoding='utf-8',errors='replace'))
best=''
def walk(x):
    global best
    if isinstance(x,str):
        if 'worker_done' in x and len(x)>len(best): best=x
    elif isinstance(x,dict):
        for v in x.values(): walk(v)
    elif isinstance(x,list):
        for v in x: walk(v)
walk(d)
io.open(f'{r}/{tag}-preamble.txt','w',encoding='utf-8').write(best)
print('preamble chars',len(best))
if not best: sys.exit(4)
PY
[ $? -ne 0 ] && exit 4
FILE="$ROOT/$R/$TAG-preamble.txt"
MSYS_NO_PATHCONV=1 orca terminal send --terminal "$H" --text "$FILE 파일을 읽고 따르라. 그 안의 Task spec과 규칙을 그대로 수행한다." --enter --json > "$R/$TAG-send.json" 2>&1
echo "send: $(grep -oE '"ok": ?(true|false)' "$R/$TAG-send.json" | head -1)"
# Some TUIs keep a long pasted line as an unsent draft. Look only at the bottom input area.
for n in 1 2 3; do
  sleep 5
  DRAFT=$(orca terminal read --terminal "$H" --json 2>/dev/null | python -c "
import json,sys
t=json.load(sys.stdin)['result']['terminal']['tail'][-6:]
print(int(any('$TAG-preamble.txt' in l and l.lstrip()[:1] in '❯›>' for l in t)))" 2>/dev/null)
  [ "$DRAFT" = "1" ] || { echo "submitted"; exit 0; }
  echo "draft left in input, pressing Enter ($n)"
  orca terminal send --terminal "$H" --text "" --enter --json > /dev/null 2>&1
done
echo "draft still present; check the terminal"; exit 5
