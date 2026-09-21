---
name: tier-harness
description: Use when the user hands over one or more PRDs, requirements documents, or issue lists and asks to implement them through Orca with difficulty-tiered worker models (high/mid/low) and separate review, QA, and approval agents. Triggers include "하네스", "harness", "tier로 나눠서 구현", "오케스트레이션으로 구현", "/tier-harness <doc> [<doc> ...]" in Claude Code, "$tier-harness <doc> [<doc> ...]" in Codex.
---

# Tier harness (Orca 오케스트레이션)

## 역할 판별

- 프롬프트에 Orca dispatch preamble(Task ID, Dispatch ID, `worker_done` 명령)이 있으면 당신은 worker다. 이 스킬을 따르지 말고 preamble만 따른다.
- 그 외에는 당신이 orchestrator다. 코드를 직접 수정하지 않는다. 분석, 분배, 대기, 합성, 보고만 한다. 예외는 3절에서 사용자가 "직접 진행"을 고른 경우뿐이다.

**REQUIRED SUB-SKILL:** 시작 전에 `orca skills get orchestration`을 읽는다. 이 스킬은 그 가이드 위에 배치와 라우팅 규칙만 얹는다.

## 입력

- 요구사항 문서 경로 1개 이상 (필수). 프롬프트에서 경로를 찾는다. 형식은 자유다. 디렉터리를 주면 그 안의 `*.md` 전부다(하위 폴더 제외). 경로가 없거나 어느 파일인지 불명확하면 사용자에게 묻는다.
- 전체 테스트·빌드 명령 (없으면 저장소에서 찾고, 못 찾으면 사용자에게 묻는다. 사용자도 없다고 하면 qa spec에 "테스트 명령 없음, 수동 검증만"이라고 적는다)

## agent CLI 표

역할마다 agent, model, effort를 고른다. 실행 명령은 이 표의 템플릿에 값을 넣어 만든다.

| agent  | 실행 파일                   | 실행 명령 템플릿                                                                                        | 초기화           | effort 허용 값                  | 상태      |
| ------ | --------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------- | --------- |
| claude | `claude`                    | `claude --model <model> --effort <effort> --dangerously-skip-permissions`                               | `/clear`         | `low medium high xhigh max`     | 검증됨    |
| codex  | `codex`                     | `codex --model <model> -c model_reasoning_effort="<effort>" --dangerously-bypass-approvals-and-sandbox` | `/new`           | `minimal low medium high xhigh ultra max` | 검증됨    |
| cursor | `agent` (구 `cursor-agent`) | `agent --model <model> --force`                                                                         | 없음             | -                               | 문서 기준 |
| gemini | `gemini`                    | `gemini --model <model> --approval-mode=yolo`                                                           | `/clear`         | -                               | 문서 기준 |
| kimi   | `kimi`                      | `kimi --model <model> --thinking --yolo`                                                                | `/clear`         | thinking 기본 on, 단계 없음     | 검증됨    |
| grok   | `grok`                      | `grok --always-approve` (model은 `~/.grok/config.toml`)                                                 | 확인 필요        | -                               | 문서 기준 |
| custom | -                           | 사용자가 준 명령                                                                                        | 사용자가 준 명령 | -                               | -         |

- "검증됨"은 Orca 1.4.205에서 이 스킬로 실제 실행한 행이다. "문서 기준" 행은 첫 사용 전에 `<실행 파일> --help`로 model 플래그와 승인 생략 플래그를 확인하고, 다르면 이 표를 고친다.
- effort가 `-`인 agent는 effort를 받지 않는다. 설정에서 `"-"`로 둔다.
- kimi의 K3 모델 id는 `kimi-code/k3`다(256K 창은 `kimi-code/k3-256k`). `kimi-k3`가 아니다. 로그인하면 `~/.kimi/config.toml`이 이 id들을 등록한다.
- kimi는 `--thinking`으로 사고 모드를 켠다. K3는 사고가 항상 켜져 있고 effort 단계 플래그는 없으므로 설정 effort는 `-`로 둔다.
- kimi는 로그인이 kimi.com(본토)으로 하드코딩된 버그가 있어, 해외 kimi.ai 구독 계정은 아래처럼 OAuth 호스트를 바꿔서 한 번 로그인해야 한다. 로그인 후 실행에는 이 변수가 필요 없다(config.toml에 base_url이 남는다).
  PowerShell: `$env:KIMI_CODE_OAUTH_HOST="https://auth.kimi.ai"; $env:KIMI_CODE_BASE_URL="https://api.kimi.ai/coding/v1"; kimi login`
- codex의 `ultra`와 `max`는 Codex 0.155 이후의 값이다. 이전 버전은 `xhigh`까지다.
- 초기화 명령이 없거나 "확인 필요"인 agent는 Task를 바꿀 때 pane을 `orca terminal close`로 닫고 그 pane 하나만 다시 만든다. 오른쪽 첫 pane이었으면 `<me>`에서 `--direction vertical`, 그 외에는 오른쪽 첫 pane에서 `--direction horizontal`로 split하고 새 handle을 `.harness/state.json`에 적는다. 세로 순서는 바뀔 수 있다.
- 모든 agent는 Orca를 실행하는 기기에 설치되고 로그인이 끝나 있어야 한다. 설치 여부는 아래로 확인한다.

```text
Get-Command claude,codex,agent,gemini,kimi,grok -ErrorAction SilentlyContinue      # Windows: PowerShell로만 확인한다
command -v claude codex agent gemini kimi grok                                     # macOS, Linux
```

- Windows에서 Git Bash의 `command -v`는 `.ps1`/`.cmd` shim(cursor의 `agent.ps1`)을 못 찾으므로 탐지에 쓰지 않는다. `agent`는 이름이 일반적이므로 `agent --version`이 답하는지 확인한다.
- codex의 model은 설치된 Codex 버전이 지원해야 한다. 첫 turn에 `requires a newer version of Codex`가 나오면 `npm i -g @openai/codex@latest`로 올린 뒤 다시 띄운다.

## 기본 라우팅

1절에서 제안 표를 만들 때 출발점이다. 설치되지 않은 agent가 있으면 설치된 agent로 바꿔서 제안한다.

| 역할         | agent  | model       | effort | 비고               |
| ------------ | ------ | ----------- | ------ | ------------------ |
| orchestrator | claude | fable       | xhigh  |                    |
| impl-high    | codex  | gpt-6-astra | max    |                    |
| impl-mid     | kimi   | kimi-code/k3 | -     | thinking on        |
| impl-low     | kimi   | kimi-code/k3 | -     | thinking on        |
| review       | claude | opus        | max    | 구현자와 다른 모델 |
| qa           | codex  | gpt-6-astra | max    |                    |
| approve      | codex  | gpt-6-astra | max    | 최종 승인          |

## 난이도 기준

위에서부터 순서대로 판정한다. 먼저 맞는 조건이 tier다.

1. **high**: 다음 중 하나라도 해당한다. 설계 판단이 필요함. 인터페이스, DB 스키마, 공용 모듈의 계약 변경. 동시성, 보안, 데이터 손실 경로. 4개 이상 파일.
2. **low**: 다음에 모두 해당한다. 명세가 완전해서 판단할 것이 없음. 리네임, 문구, 설정값, 단순 함수 중 하나. 3개 이하 파일.
3. **mid**: 나머지 전부. 기존 패턴을 따라 구현하고 테스트를 추가하는 일반 작업.

재작업 Task는 원래 tier보다 한 단계 위로 올린다. high는 high로 유지한다.

## 절차

명령 규칙: Windows에서 Claude Code는 Bash 도구(Git Bash)로, Codex는 PowerShell로 실행한다. 큰따옴표로 감싼 인자 안에서는 큰따옴표를 쓰지 않는다. `--command` 값과 JSON 배열은 작은따옴표로 감싸고, 그 안의 큰따옴표는 그대로 둔다. PowerShell 5.1에서는 JSON 배열의 안쪽 큰따옴표를 `--deps '[\"t1\"]'`처럼 백슬래시로 이스케이프한다. 아래 예시에서 `$ORCA_TERMINAL_HANDLE`처럼 셸별 표기가 갈리는 곳은 각각 적어 두었다.

### 1. 설정

프롬프트에 "설정 확인됨"이 있고 `.harness/config.json`이 있으면 이 절을 건너뛴다.

`.harness/config.json`이 이미 있으면 roles를 표로 보여주고 "그대로 사용 / 다시 설정"을 묻는다. docs는 묻지 않고 이번 프롬프트의 문서 목록으로 덮어쓴다. 없거나 다시 설정이면 아래 순서다. 사용자가 "자동"이라고 했으면 3번의 질문을 생략하고 제안 표를 그대로 쓴다.

1. agent CLI 표의 실행 파일을 전부 검사해 설치된 agent 목록을 만든다. custom은 검사하지 않고 설치된 것으로 본다.
2. 기본 라우팅을 설치된 agent만으로 채운 제안 표를 만든다. 설치된 agent 목록과 함께 보여준다.
3. 사용자에게 묻는다. Claude Code면 AskUserQuestion으로 "표대로 진행 / 수정" 두 선택지를 준다. 그 외 CLI는 채팅으로 묻는다. 수정은 "review를 claude opus high로"처럼 행 단위로 받고, 반영한 표를 다시 보여준 뒤 다시 묻는다. 확인될 때까지 반복한다.
4. 검증한다. 모든 행의 agent가 설치됨. effort가 그 agent의 허용 값. review의 agent+model이 impl-high, impl-mid, impl-low 어느 것과도 다름. 하나라도 틀리면 틀린 값이 들어간 표를 이유와 함께 보여주고 3번으로 돌아간다.
5. `.harness/config.json`에 저장한다. `custom` agent 행은 `"command"`와 `"clear"`를 함께 적는다.

```json
{
  "docs": ["docs/prd-auth.md", "docs/prd-billing.md"],
  "test_command": "npm test",
  "roles": {
    "orchestrator": { "agent": "claude", "model": "fable",       "effort": "xhigh" },
    "impl-high":    { "agent": "codex",  "model": "gpt-6-astra", "effort": "max" },
    "impl-mid":     { "agent": "kimi",   "model": "kimi-code/k3", "effort": "-" },
    "impl-low":     { "agent": "kimi",   "model": "kimi-code/k3", "effort": "-" },
    "review":       { "agent": "claude", "model": "opus",        "effort": "max" },
    "qa":           { "agent": "codex",  "model": "gpt-6-astra", "effort": "max" },
    "approve":      { "agent": "codex",  "model": "gpt-6-astra", "effort": "max" }
  }
}
```

아래에서 `<cmd_high>`, `<cmd_review>` 등은 config의 해당 역할을 agent CLI 표 템플릿에 넣어 만든 실행 명령이다.

6. orchestrator 인계. 현재 세션의 agent는 이 스킬을 실행 중인 CLI(Claude Code면 claude, Codex면 codex)이고, model은 시스템 프롬프트나 `/status`로 확인한다. config의 orchestrator가 현재 세션과 agent 또는 model이 다르면 새 탭에 그 orchestrator를 띄우고 넘긴다. effort만 다르면 인계하지 않는다. 현재 세션은 인계 receipt를 사용자에게 보고하고 끝낸다. 같으면 2절로 간다.

```text
orca terminal create --worktree current --title "orchestrator" --command '<cmd_orchestrator>' --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 120000 --json
orca terminal send --terminal <handle> --text "<SKILL.md 절대 경로>를 읽고 orchestrator로 실행하라. 설정 확인됨. .harness/config.json의 docs를 요구사항 문서로 쓴다." --enter --json
```

SKILL.md 절대 경로는 이 파일이 실제로 있는 곳이다. Claude Code는 스킬 로드 시 표시된 base directory, Codex는 `/skills` 목록의 경로에서 얻는다. 기본 설치 위치는 `~/.agents/skills/tier-harness/SKILL.md`다.

### 2. 준비

```text
orca status --json
echo $ORCA_TERMINAL_HANDLE      # = <me>. PowerShell은 $env:ORCA_TERMINAL_HANDLE
```

`--terminal`을 생략하면 UI에서 선택된 터미널을 가리키므로, 모든 terminal 명령에 handle을 명시한다.

codex를 쓰는 역할이 하나라도 있으면, 이 저장소에서 codex를 한 번 실행해 trust 대화상자("Do you trust the contents of this directory?")를 미리 넘겨 둔다. 신뢰하지 않은 저장소에서는 모든 codex pane이 이 대화상자에서 멈추고, Orca는 그 상태의 터미널에 보내는 `terminal send`를 `agent_prompt_blocked`로 거부하므로 사용자가 직접 눌러야만 풀린다.

### 3. 분석

config의 docs를 전부 읽고 하나의 Task 목록을 만든다. 문서 제목은 첫 H1이고, 없으면 파일명이다. 문서끼리 요구가 충돌하면 Task를 만들기 전에 사용자에게 묻는다. Task 하나는 worker 하나가 한 번에 끝낼 수 있는 단위다.
각 Task spec은 Source(출처 문서 경로) / Target / Change / Constraints / Ownership(수정 가능한 파일) / Acceptance(검증 명령)를 반드시 포함하고, 마지막에 7절의 구현 템플릿을 그대로 붙인다.
spec에 tier와 모델 이름은 적지 않는다.

의존 관계: B가 A의 결과를 쓰거나 A와 같은 파일을 수정하면 B는 A에 의존한다. 문서가 달라도 같다. 파일이 겹치는데 논리 순서가 없으면 tier가 낮은 쪽을 앞에 둔다. 겹치지 않으면 순서가 없다. 의존하는 Task는 4절에서 만들지 않고, 선행 Task 전부의 review가 `succeeded`된 시점에 `--deps '["<선행 task_id>"]'`로 task-create 한다. 그래야 재작업 중인 Task와 같은 파일을 동시에 건드리지 않는다.

분석 결과를 `| # | tier | doc | title | files | deps |` 표로 사용자에게 보여주고 확인을 받는다. 사용자가 "자동" 또는 "바로 실행"이라고 했으면 확인 없이 진행한다.

Task가 2개 이하이고 전부 low면 하네스의 고정 비용(pane, review, qa, approve)이 작업보다 크다. 표와 함께 "하네스 없이 이 세션에서 직접 진행할까요?"를 같이 묻는다. 직접 진행을 고르면 orchestrator가 그 자리에서 구현하고 Acceptance를 실행하고 커밋한 뒤 끝낸다. "자동"이면 묻지 않고 하네스로 진행한다.

### 4. Run과 Task 생성

```text
orca orchestration run-create --objective "<문서 제목들을 + 로 이은 것>" --json
orca orchestration task-create --spec "<Task 본문>" --task-title "[high] <title>" --deps '[]' --json
orca orchestration task-list --ready --brief --json
```

제목 형식: 구현 `[high] <title>`, 재작업 `[mid] <title> (rework 1)`, 리뷰 `[review] <title>`, `[qa] <objective>`, `[approve] <objective>`.

run_id, tier별 pane handle, 각 pane의 현재 dispatch_id, qa·approve 회차를 `.harness/state.json`에 바뀔 때마다 덮어쓴다. 컨텍스트가 비거나 세션이 다시 시작되면 이 파일과 `orca orchestration task-list --json`, `orca orchestration worker-list --json`으로 상태를 복구해 6절부터 이어 간다.

### 5. 배치

레이아웃: 왼쪽은 orchestrator, 오른쪽은 tier pane이다. review, qa, approve는 새 탭이다. tier pane은 미리 만들지 않고 그 tier의 ready Task가 처음 생길 때 만들며, 만든 뒤에는 실행이 끝날 때까지 유지한다. 작은 실행에서는 pane이 1개일 수도 있다.

```text
[orchestrator] | [첫 tier pane ]
               | [둘째 tier pane]
               | [셋째 tier pane]
```

이 빌드의 `terminal split --direction`은 `vertical`이 좌우 분할, `horizontal`이 상하 분할이다. 도움말 문구와 반대이므로 아래 순서를 그대로 쓴다. `--command`에는 바로 종료되는 명령을 넣으면 "Timed out waiting for split pane handle"로 실패한다.

**pane 만들기.** 오른쪽 첫 pane은 `<me>`에서 vertical로, 그다음 pane은 오른쪽 첫 pane에서 horizontal로 나눈다. 세로 순서는 만든 순서를 따른다. tier마다 한 번만 만들고 handle을 `.harness/state.json`에 적는다.

```text
orca terminal split --terminal <me>    --direction vertical   --command '<cmd_tier>' --json   # 첫 pane. 결과 handle = <first>
orca terminal split --terminal <first> --direction horizontal --command '<cmd_tier>' --json   # 둘째, 셋째 pane
orca terminal wait --terminal <새 handle> --for tui-idle --timeout-ms 120000 --json
```

pane 크기는 CLI로 맞출 수 없다. 사용자가 pane을 우클릭해 "Equalize pane sizes"를 누르거나 Settings → Shortcuts에서 `terminal.equalizePaneSizes`에 키를 배정한다.

**Task 투입.** ready Task의 tier에 맞는 pane에 진행 중인 Dispatch가 없을 때만 넣는다. pane 하나에 Task 하나씩이다. `<clear>`는 그 pane agent의 초기화 명령이다.

```text
orca terminal send --terminal <pane> --text "<clear>" --enter --json
orca terminal wait --terminal <pane> --for tui-idle --timeout-ms 60000 --json
orca orchestration worker-start --task <task_id> --worktree current --terminal <pane> --json
```

- 첫 투입에는 초기화가 필요 없다. 두 번째 Task부터 이전 Task의 컨텍스트를 비우기 위해 보낸다.
- `wait` 결과의 `satisfied`가 `true`이고 `orca terminal read --terminal <pane> --json`의 마지막 화면이 agent 입력 프롬프트일 때만 `worker-start`를 호출한다. `blockedReason`이 `agent-interactive-prompt`이거나 화면에 확인 대화상자·로그인 화면이 떠 있으면 사용자에게 보고하고 사용자가 넘길 때까지 기다린다. 그 터미널에 `terminal send`를 보내도 `agent_prompt_blocked`로 거부된다. `satisfied`가 `false`면 timeout을 두 배로 한 번 더 기다리고, 그래도 안 되면 사용자에게 보고한다.
- 동시 실행은 tier당 1개, 기본 3개다. 같은 tier의 ready Task가 3개 이상 쌓이면 그 pane을 `--direction vertical`로 한 번 더 나눠 그 tier의 worker를 하나 더 둔다. 그 외에는 나누지 않는다.

**review / qa / approve는 새 탭이다.** 탭은 Task마다 만들고 끝나면 닫는다.

```text
orca terminal create --worktree current --title "review <task#>" --command '<cmd_review>' --json
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 120000 --json
orca orchestration worker-start --task <task_id> --worktree current --terminal <handle> --json
```

### 6. 대기 루프

```text
orca orchestration check --wait --types "worker_done,escalation,question" --timeout-ms 540000 --json
```

`--timeout-ms`는 orchestrator가 쓰는 셸 도구의 timeout보다 짧아야 한다. Claude Code는 Bash 도구의 timeout을 600000으로 올려서 호출한다(상한). Codex는 shell 도구 호출마다 `timeout_ms`를 600000으로 넣는다. 기본값으로 두면 대기 중에 명령이 끊긴다.

Delivery 안의 모든 메시지를 처리한 뒤에만 ack한다.

- `question`: `orca orchestration reply --id <message_id> --body "<답>" --json`. orchestrator가 답을 모르면 사용자에게 묻고 답을 받은 뒤 reply한다. 그동안 다른 메시지는 계속 처리한다.
- `escalation`: 원인을 읽고 `send --to dispatch:<id>`로 지시하거나 사용자에게 올린다.
- `worker_done`: `--outcome`을 확인한다. 구현 worker가 `succeeded`인데 body에 커밋 sha가 없으면 `git log -3 --format=%H -- <Ownership 파일>`로 찾고, 커밋이 없으면 `failed`로 취급한다. 구현 worker가 `failed`면 body의 사유를 리포트 대신 붙여 7절 1번의 재작업 규칙을 그대로 적용한다. 다음 단계 Task를 만든 뒤 터미널의 다음 주인을 정한다.
  - tier pane이면: 같은 tier의 ready Task가 있으면 retain 없이 5절의 "Task 투입"으로 바로 재사용한다. 없으면 `orca orchestration worker-retain --dispatch <dispatch_id> --json`으로 pane을 살려 둔다. `worker-release`는 pane을 닫으므로 8절에서만 쓴다.
  - 탭 worker(review, qa, approve)면: `orca orchestration worker-release --dispatch <dispatch_id> --json`으로 탭을 닫는다.
- 처리 후: `orca orchestration check --ack <delivery_id> --wait --types "worker_done,escalation,question" --timeout-ms 540000 --json`

빈 결과나 timeout은 실패가 아니다. 빈 대기가 3번 연속이면 `orca orchestration worker-list --include-remote --json`으로 각 행의 `projection.nextAction`을 따른다.

### 7. 단계별 Task 규칙

**implement → review → qa → approve** 순서로 흐른다. 각 단계는 앞 단계 Task를 `--deps`로 건다.

1. **review** (구현 Task마다 1개, `review` 역할): 구현 Task가 `succeeded`면 만든다. spec에 구현 Task의 spec 전문과 커밋 sha를 넣고 review 템플릿을 붙인다.
   `failed`면 리포트 경로를 spec에 붙인 재작업 Task를 새로 만들고 tier를 한 단계 올려 다시 투입한다. 같은 Task의 재작업은 최대 2회다. 그 뒤에는 사용자에게 올린다. 답을 기다리는 동안 그 Task는 보류하고, 그 pane에는 다른 ready Task를 넣거나 retain한다. 후속 Task는 deps 때문에 ready가 되지 않으므로 그대로 둔다. 사용자가 결정하면 재작업 Task를 만들거나, 그 Task와 후속 Task를 제외하고 진행한다.
2. **qa** (전체 1개, `qa` 역할): 모든 review가 `succeeded`면 만든다. spec에 config의 docs 전부와 전체 테스트·빌드 명령을 넣고 qa 템플릿을 붙인다. `failed`면 리포트의 항목별로 재작업 Task를 만든다.
3. **approve** (전체 1개, `approve` 역할): qa가 `succeeded`면 만든다. spec에 config의 docs 전부와 review·qa 리포트 경로를 넣고 approve 템플릿을 붙인다. `failed`면 사유별로 재작업 Task를 만들어 1번부터 반복한다.

리포트 경로는 `.harness/reports/<구현 task_id>-review.md`, `.harness/reports/qa-<회차>.md`, `.harness/reports/approve-<회차>.md`다. 회차는 1부터 세고, qa와 approve를 새로 만들 때마다 각각 1씩 올린다. `.harness/`는 커밋하지 않는다.

**역할별 spec 템플릿.** 아래 블록을 spec 끝에 그대로 붙인다. `<...>`는 orchestrator가 채운다. "묻는다"는 dispatch preamble이 알려주는 질문 방법을 뜻한다.

구현:

```text
규칙
- Ownership에 적힌 파일만 수정한다. 다른 파일이 필요하면 수정하지 말고 묻는다.
- Change에 없는 변경은 하지 않는다. 리팩터링, 포맷 정리, 부수 개선을 하지 않는다.
- Acceptance 명령을 실제로 실행한다. 통과시키려고 테스트나 기대값을 고치지 않는다.
- 명세가 불명확한 지점은 추측하지 말고 묻는다.
- 완료 시 Ownership 파일만 `git commit -m '<task_id>: <title>'`으로 커밋한다. index.lock 오류면 몇 초 뒤 다시 시도한다.
- worker_done body에 커밋 sha, 실행한 Acceptance 명령과 출력 마지막 10줄, 하지 않은 것을 적는다.
```

review:

```text
규칙
- 코드를 수정하지 않는다. `git show <sha>`를 위 spec과 대조한다.
- 확인 순서: (1) Change의 각 항목이 구현됐고 Acceptance가 실제로 통과하는가(직접 실행). (2) 커밋에 Ownership 밖 파일이 있는가. (3) 새 동작에 테스트가 있고 기존 테스트를 약화시키지 않았는가. (4) 호출자, 공용 인터페이스, 데이터 경로에 회귀 위험이 있는가.
- 지적은 `파일:줄 | blocking 또는 minor | 문제 | 수정안` 형식으로 한 줄씩 `.harness/reports/<task_id>-review.md`에 쓰고 worker_done의 --report-path로 제출한다.
- blocking이 하나라도 있으면 --outcome failed, 없으면 succeeded. 스타일과 취향은 minor로만 적고 failed 사유로 삼지 않는다.
```

qa:

```text
규칙
- 코드를 수정하지 않는다.
- 전체 테스트·빌드 명령을 실제로 실행하고 출력 마지막 30줄을 리포트에 붙인다.
- 요구사항 문서의 항목마다 수동 검증 시나리오를 하나씩 만들어 실행하고 `항목 | 시나리오 | 결과 | 근거`로 적는다.
- 실패 항목마다 재현 절차와 관찰된 출력을 적는다.
- 리포트는 `.harness/reports/qa-<회차>.md`에 쓰고 worker_done의 --report-path로 제출한다. 실패 항목이 하나라도 있으면 --outcome failed.
```

approve:

```text
규칙
- 코드를 수정하지 않는다.
- 요구사항 문서마다 항목을 표로 만들고 `항목 | 충족 또는 미충족 | 근거(커밋 sha, 리포트 경로, 테스트 출력)`를 채운다.
- review와 qa 리포트에 해결되지 않은 blocking이나 실패 항목이 남아 있는지 확인한다.
- 남은 위험(데이터 손실, 보안, 되돌리기 어려운 변경)을 따로 적는다.
- 리포트는 `.harness/reports/approve-<회차>.md`에 쓰고 worker_done의 --report-path로 제출한다. 미충족이나 미해결 blocking이 하나라도 있으면 --outcome failed, 아니면 succeeded가 승인이다.
```

### 8. 종료

approve가 `succeeded`면 tier pane을 전부 마지막 dispatch로 release한다. 추가로 나눈 pane도 같다.

```text
orca orchestration worker-release --dispatch <pane의 마지막 dispatch_id> --json   # pane마다
orca orchestration worker-list --terminal-state reclaimable --json
```

두 번째 명령의 결과가 비어야 끝난다. 사용자에게 문서별, Task별로 결과, 증거(테스트 출력이나 리포트 경로), 미해결 항목을 보고한다.

사용자가 중간에 중단을 요청하면 진행 중인 dispatch마다 `send --to dispatch:<id>`로 "커밋하지 말고 멈춰라"를 보낸 뒤, 위와 같은 순서로 pane과 탭을 정리하고 남은 Task와 마지막 커밋 sha를 보고한다. `.harness/state.json`은 남겨 둔다.

## 규칙

- 리뷰어는 구현자와 다른 모델이어야 한다. 설정을 바꿀 때도 이 조건은 유지한다.
- worker는 `--worktree current`로 같은 checkout에서 일한다. 파일 소유권이 겹치는 Task를 동시에 돌리지 않는다. tier나 출처 문서가 달라도 같다.
- tier별 pane handle과 각 pane의 현재 dispatch_id는 `.harness/state.json`이 기준이다. handle이 `terminal_handle_stale`이면 `orca terminal list --worktree current --json`으로 다시 찾는다.
- `worker-start`가 실패하면 재실행하지 않는다. receipt의 `failedStage`를 읽고 `orca skills get orchestration --reference references/recovery-and-cleanup.md`를 따른다.
- 모든 Orca 명령은 `--json`으로 실행하고 receipt를 읽는다. 출력이 있었다는 사실이 성공을 뜻하지 않는다.
