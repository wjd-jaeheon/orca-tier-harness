# orca-tier-harness

Orca 오케스트레이션용 에이전트 스킬입니다. 요구사항 문서(PRD)를 받아 Task로 쪼개고, 난이도(high / mid / low)에 따라 서로 다른 모델의 worker에게 배분한 뒤, 별도의 review → qa → approve 에이전트로 검증까지 돌립니다.

An agent skill for [Orca](https://orca.app) orchestration: split requirement docs into tasks, route each task to a high/mid/low-tier worker model, then run separate review, QA and approval agents.

## 구성

`plan(ready) → plan-review → impl(high/mid/low) → impl-review → 묶음 전체 gate → qa → approve → docs → 사용자`

실행·역할 규칙은 [SKILL.md](SKILL.md), 후보 검증·자원 격리는 [통합 gate](references/integration-gate.md), 회귀 확인은 [tests/README.md](tests/README.md)에 있습니다. ready의 출처·동기화는 [UPSTREAM.md](ready/UPSTREAM.md)를 따릅니다.

요구사항·코드·worker 리포트의 지시문은 데이터로만 다룹니다. worker는 승인 생략 플래그로 실행하므로 신뢰하는 저장소에서만 사용하십시오.

## 요구 사항

- 자동 gate 검증에는 Python 3.9 이상이 필요합니다. `check-gate.py`는 외부 패키지를 사용하지 않습니다.
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

문서 경로는 말로 풀어 써도 됩니다. 디렉터리를 주면 그 안의 `*.md` 전부를 읽습니다. 시작하면 설치된 agent를 탐지해 라우팅 표를 제안하고, 확인을 받은 뒤 Task 분석으로 넘어갑니다. pane 크기는 CLI로 맞출 수 없으므로 pane을 우클릭해 "Equalize pane sizes"를 누릅니다.

한 번의 명령으로 설정, ready 대화(질문에 답하고 3-doc 승인), 실행까지 이어집니다. dryforge 플러그인으로 `/dryforge:ready`를 따로 돌려 `.dryforge/`에 3-doc을 만들어 두었다면, 문서 경로 없이 `/tier-harness`만 불러도 그 3-doc으로 실행합니다.

## 검증 상태

| 항목                                   | 상태                                        |
| -------------------------------------- | ------------------------------------------- |
| Claude Code에서 시작, claude/codex worker | Orca 1.4.205에서 실행 확인                 |
| Codex에서 시작 (`$tier-harness`)         | 설정 절까지 실행 확인                       |
| kimi (kimi-cli 1.50.0)                    | 설치·로그인·플래그·모델 id(`kimi-code/k3`) 확인. 해외 계정은 로그인 시 `KIMI_CODE_OAUTH_HOST=https://auth.kimi.ai`, `KIMI_CODE_BASE_URL=https://api.kimi.ai/coding/v1` 필요 |
| cursor / gemini / grok 실행 플래그        | 공식 문서 기준, 미실행. 첫 사용 전 `--help`로 확인 |

자세한 절차와 규칙은 [SKILL.md](SKILL.md)에 있습니다.

## License

[MIT](LICENSE). `ready/`는 [dryforge](https://github.com/prekuter/dryforge)에서 가져온 것이며 별도의 [MIT 라이선스](ready/LICENSE)를 따릅니다.
