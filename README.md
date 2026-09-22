# orca-tier-harness

Orca 오케스트레이션용 에이전트 스킬입니다. 요구사항 문서(PRD)를 받아 Task로 쪼개고, 난이도(high / mid / low)에 따라 서로 다른 모델의 worker에게 배분한 뒤, 별도의 review → qa → approve 에이전트로 검증까지 돌립니다.

An agent skill for [Orca](https://orca.app) orchestration: split requirement docs into tasks, route each task to a high/mid/low-tier worker model, then run separate review, QA and approval agents.

## 구성

흐름: `plan(ready) → plan-review → impl(high/mid/low) → impl-review → qa → approve → 사용자`. 각 화살표가 검증 단계이고, 사람이 approve의 최종 검토자입니다.

```text
[orchestrator] | [high]      plan / plan-review / impl-review / qa / approve 는 새 탭
               | [mid ]      tier pane은 그 tier의 Task가 처음 생길 때 만들어짐
               | [low ]
```

- orchestrator는 코드를 직접 수정하지 않고 대화, 분배, 대기, 보고만 합니다. Task 분해는 planner가 하고 plan-review가 다른 모델로 검증합니다.
- 요구사항 문서를 받으면 planner worker가 [dryforge](https://github.com/prekuter/dryforge)의 `ready` 절차(이 저장소의 `ready/`에 동봉, MIT)를 수행해 3-doc(`.dryforge/handoff.md`, `spec.md`, `plan.md`)을 만듭니다. ready의 질문과 승인 요청은 Orca question으로 orchestrator에게 오고, orchestrator가 사용자에게 묻고 답을 돌려줍니다. 사용자는 orchestrator와만 대화합니다. `risk`(RISKY / MECHANICAL / NONE)가 tier(high / mid / low)로, `depends`가 Task 의존으로 옮겨집니다. dryforge의 `go`는 쓰지 않고 이 스킬이 Orca에서 실행합니다. 동봉본의 출처와 재동기화 방법은 [ready/UPSTREAM.md](ready/UPSTREAM.md)에 있습니다.
- 구현 worker는 tier마다 하나씩 둔 git worktree(`.harness/worktrees/<tier>`)에서 일합니다. 완료된 Task는 머지 게이트(Ownership 밖 파일 없음)와 통합 게이트(전체 테스트 통과)를 지나야 base에 올라가고, 그 다음에 review가 붙습니다.
- 모든 역할은 판단 근거를 리포트나 worker_done에 남겨서, 다음 단계가 검증할 수 있게 합니다.
- Task가 2개 이하이고 전부 low면 하네스 없이 직접 진행할지 먼저 묻습니다.
- 역할마다 agent CLI(claude, codex, cursor, gemini, kimi, grok, custom)와 model, effort를 시작할 때 고릅니다. 선택 결과는 `.harness/config.json`에 저장되어 다음 실행에서 재사용됩니다.
- impl-review는 구현자와, plan-review는 planner와 다른 모델이어야 한다는 검증이 붙습니다.
- worker가 받는 Task spec 끝에는 역할별 규칙 템플릿(planner, plan-review, 구현, impl-review, qa, approve)이 붙어서, 어떤 CLI의 모델이든 같은 완료·실패 기준으로 일합니다.
- 선택한 orchestrator가 현재 세션과 다르면 새 탭에 그 agent를 띄워 인계합니다.
- 3-doc은 Task를 만들기 전에 `scripts/check-3doc.py`로 결정론적으로 검사합니다(그래프 파싱, 순환, 없는 id, 본문·그래프 불일치, `risk` 값). 통과한 3-doc의 해시를 기록해 실행 중 문서가 바뀌면 멈춥니다.
- 요구사항 문서, 코드, worker 리포트 안의 문장은 데이터로만 다룹니다. 그 안에 에이전트를 향한 지시문이 있어도 따르지 않습니다. worker는 승인 생략 플래그로 실행되므로 신뢰하는 저장소에서만 쓰십시오.
- `tests/`에 픽스처와 dry run 절차가 있습니다. 스킬을 고칠 때 전후를 비교하는 용도입니다.

## 요구 사항

- Orca 1.4.205 이상. 이 스킬은 `orca terminal split`, `orca orchestration worker-start --terminal` 등 Orca CLI 위에서 동작합니다.
- 역할에 배정할 agent CLI가 Orca를 실행하는 기기에 설치되고 로그인되어 있어야 합니다.
- Windows에서는 PowerShell `Get-Command`로 설치 여부를 확인합니다. Git Bash의 `command -v`는 `.ps1` shim을 찾지 못합니다.

## 설치

Codex, Copilot CLI, Gemini CLI는 `~/.agents/skills`를 직접 읽습니다.

```text
git clone https://github.com/wjd-jaeheon/orca-tier-harness ~/.agents/skills/tier-harness
```

Claude Code는 `~/.claude/skills`를 읽으므로 링크를 하나 둡니다.

```text
# macOS, Linux
ln -s ~/.agents/skills/tier-harness ~/.claude/skills/tier-harness

# Windows (PowerShell)
New-Item -ItemType Junction -Path "$HOME\.claude\skills\tier-harness" -Target "$HOME\.agents\skills\tier-harness"
```

## 사용

```text
/tier-harness docs/prd-auth.md docs/prd-billing.md     # Claude Code
$tier-harness docs/prd-auth.md docs/prd-billing.md     # Codex
```

문서 경로는 말로 풀어 써도 됩니다. 디렉터리를 주면 그 안의 `*.md` 전부를 읽습니다. 시작하면 설치된 agent를 탐지해 라우팅 표를 제안하고, 확인을 받은 뒤 Task 분석으로 넘어갑니다.

한 번의 명령으로 설정, ready 대화(질문에 답하고 3-doc 승인), 실행까지 이어집니다. dryforge 플러그인으로 `/dryforge:ready`를 따로 돌려 `.dryforge/`에 3-doc을 만들어 두었다면, 문서 경로 없이 `/tier-harness`만 불러도 그 3-doc으로 실행합니다.

## 검증 상태

| 항목                                   | 상태                                        |
| -------------------------------------- | ------------------------------------------- |
| Claude Code에서 시작, claude/codex worker | Orca 1.4.205에서 실행 확인                 |
| Codex에서 시작 (`$tier-harness`)         | 설정 절까지 실행 확인                       |
| kimi (kimi-cli 1.50.0)                    | 설치·로그인·플래그·모델 id(`kimi-code/k3`) 확인. 해외 계정은 로그인 시 `KIMI_CODE_OAUTH_HOST=https://auth.kimi.ai` 필요 |
| cursor / gemini / grok 실행 플래그        | 공식 문서 기준, 미실행. 첫 사용 전 `--help`로 확인 |

자세한 절차와 규칙은 [SKILL.md](SKILL.md)에 있습니다.

## License

[MIT](LICENSE). `ready/`는 [dryforge](https://github.com/prekuter/dryforge)에서 가져온 것이며 별도의 [MIT 라이선스](ready/LICENSE)를 따릅니다.
