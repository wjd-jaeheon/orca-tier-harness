# 리뷰 선행과 통합 gate

6절의 구현 완료 처리와 7절의 검토·qa에서 읽는다. 전체 시험을 줄이지 않고, 실패할 변경에 대한 전체 시험과 같은 후보의 중복 실행을 줄인다.

## 고정된 검토와 후보

1. 구현 완료 시 `dispatch_base_sha`부터 완료 SHA까지의 변경으로 Ownership을 검사하고 `harness/keep/<task_id>/<회차>`에 보존한다. 현재 base와 비교해 다른 Task의 변경을 섞지 않는다. worker의 `succeeded`는 구현 완료이며 통합 승인이 아니다.
2. 검토자는 자신의 worktree에서 지정된 전체 SHA를 checkout한다. tier worker나 base의 변경 중인 디렉터리에서 시험하지 않는다. 묶음 검토도 각 Task의 SHA를 따로 확인하고, Task별 판정·검사 범위와 교차 지적을 남긴다. 검토 worktree는 해당 검토가 끝나기 전에 reset하거나 재사용하지 않는다.
3. gate가 비면 **이미 검토가 끝난 변경**과 7절의 low 검토 생략 대상을 현재 준비된 수만큼 묶는다. 상한은 기존 `review_batch_size`다. 묶음을 채우려고 기다리지 않는다. 후속을 막는 Task부터 선택하고, 미승인 선행 변경에 의존하는 Task는 넣지 않는다. gate 중에는 구현·리뷰를 계속하고 다음 후보의 대기 목록만 갱신한다.
4. base의 전체 SHA를 고정하고 별도 candidate worktree에서 구성원 keep ref를 합친다. `.harness/state.json`에 후보 ID, base SHA, 구성원 Task·SHA, 후보 SHA, worktree 경로를 남긴다. checkout·의존성 설치·프로젝트 환경을 확인한다. 충돌은 이 후보에서만 abort하고 해당 Task를 재작업으로 돌린다. 충돌 해결이나 재적용으로 검토된 diff가 달라지면 그 변경을 다시 검토한다. 임의로 코드를 고쳐 통합하지 않는다.
5. 이 후보에서 새로 충족되는 regen barrier를 먼저 실행하고 생성 변경을 커밋한다. 생성 변경도 Ownership과 해당 검증으로 확인한 뒤 **최종 후보 SHA를 고정하고 전체 gate**를 돌린다. gate 뒤에 regen 커밋을 붙여 검증되지 않은 SHA를 승격하지 않는다.
6. 검토·gate 동안 후보 소스는 변경하지 않는다. 다른 worker의 쓰기 대상에서 제외하고 시작·종료 HEAD와 clean 상태를 기록한다. 앞뒤 SHA가 같아도 중간 변경이 허용되는 것은 아니다. 로그·상태는 후보 소스 밖의 attempt 디렉터리에 둔다. 무시되는 빌드 산출물과 소스 변경은 구분한다.
7. 승격 직전 base가 기록한 SHA이고 깨끗한지 다시 확인한다. base 변경 권한을 가진 orchestrator 하나만 이 확인과 `git merge --ff-only <candidate_sha>`를 수행한다. 새 merge commit을 만들지 않는다. base가 바뀌면 오래된 결과를 적용하지 않고 새 base로 후보를 다시 만들고 검증한다. 외부 동시 쓰기가 있으면 승격을 중지한다. 통과한 정확한 후보만 승인 base로 기록한다.

입력 절에서 사용자가 자동 시험·빌드 명령이 없고 수동 검증만 있음을 확인한 프로젝트는 자동 gate 결과를 만들지 않는다. 이 경우에만 고정 후보의 리뷰 → 수동 qa·approve → 동일 SHA 승격으로 진행하고 자동 gate는 `not_applicable`로 보고한다. 자동 시험이 있는 프로젝트의 실패·환경 부재·필수 누락을 이 예외로 돌리지 않는다.

검토용 worktree는 `.harness/worktrees/review-<n>`, gate용은 `.harness/worktrees/candidate-<id>`처럼 서로 구분한다. 터미널은 해당 경로의 `--worktree path:<절대 경로>`로 만들고 receipt의 경로를 확인한다. 리뷰어 탭을 재사용할 때는 같은 경로 안에서 이전 검토 종료를 확인한 후 checkout한다. 새로운 경로로 옮기면 터미널도 그 경로로 새로 만든다. 실패 후보와 keep ref는 원인 확인 전에 지우지 않는다.

## 실패와 재시도

- 묶음 gate가 실패하면 승인 base는 그대로 두고 후보·로그를 보존한다. 실패 파일의 구성원별 재실행은 진단이며 통합 gate를 대신하지 않는다. 모두 단독 통과해도 상호작용 문제인지 환경 문제인지는 아직 미확인이다.
- 구성원을 뺄 때는 그 변경을 필요로 하는 후속 변경도 뺀다. 새 구성으로 만든 후보는 전체 gate를 다시 통과해야 한다. 실패를 임의의 마지막 Task 탓으로 돌리지 않는다. 조정자가 원인과 재작업 소유를 정한다.
- 모든 실행은 새 attempt ID와 새 디렉터리를 쓴다. 기존 디렉터리가 있으면 다른 ID를 만들고 덮어쓰지 않는다. footer만 있거나 조정자 상태와 결과가 어긋나면 `unverified`다. 실제 실행 프로세스와 자식의 종료를 확인하기 전에는 같은 자원으로 재실행하지 않는다.
- 후속 Task는 승인 base에서 시작한다. 사용자가 후보 기반의 선행 작업을 명시적으로 허용한 경우에만 기반 후보 SHA를 spec·state에 기록해 시작한다. 후보가 바뀌거나 실패하면 후속 완료 판정도 무효화하고 다시 검증한다.

## 자원과 환경

worker·reviewer·gate·qa의 spec에 사용할 DB/스키마, 포트, 임시 경로, 무거운 시험 구간의 소유자를 넣는다. 프로젝트의 기존 자원 제어 helper를 사용하며 전체 `npm test`를 일괄 잠그지 않는다. 구간별 제어가 없으면 먼저 프로젝트의 시험 helper에 구현하고 검증한다. 준비 전에는 충돌하는 무거운 명령을 겹쳐 실행하지 않고 조정자가 순서를 정한다. 가벼운 구현과 코드 검토는 계속한다. gate에 무조건 우선권을 주지 않는다.

여러 Run이 같은 머신 자원을 쓰면 같은 자원 소유 기록과 잠금을 사용해야 한다. Run별 state만으로 머신 전체 잠금을 구현했다고 보지 않는다. OS 프로세스 PID·시작 시각·attempt를 연결하고, 자원 사용 자식까지 종료가 확인돼야 잠금을 회수한다. heartbeat 만료·조정자 중단·시간 초과만으로 회수하지 않는다. 부모와 자식이 같은 잠금을 중복 획득하지 않게 한다. 해당 프로세스의 상태가 미확인이면 자원을 재할당하지 않는다.

전용 DB/스키마도 같은 PG 인스턴스의 재시작은 공유한다. 다른 실행이 사용 중인 서버를 내리거나 재시작하지 않는다. 서버 수명 소유자를 정하거나 별도 인스턴스를 쓴다. recovery·OOM을 환경 문제로 분류해도 gate 통과로 바꾸지 않는다. 원인을 확인하고 영향받은 후보를 다시 검증한다.

필수 환경 조건과 **실제로 등록·실행돼야 할 시험 ID**를 프로젝트의 기존 시험 설정·hard gates에서 정한다. ID는 파일·suite 등으로 구분해 중복되지 않게 한다. 필수 시험은 skip뿐 아니라 미등록·미실행도 실패다. 날짜 fixture의 기준 기간은 프로젝트에서 고치며 이름별 실패 차감이나 harness의 특정 프로젝트 예외로 처리하지 않는다. 환경은 수명이 관리되는 설정에서 공급하고 값 대신 설정 유무와 비밀이 아닌 자원 ID만 기록한다.

## 판정 기록과 검증기

프로젝트 runner가 `.harness/gates/<attempt_id>/`에 다음 파일을 쓴다. 조정자가 결과를 산문에서 추정하거나 성공 JSON을 대신 작성하지 않는다. runner는 각 단계의 실제 exit와 reporter의 시험 결과를 수집한다. `echo`나 마지막 빌드 성공으로 앞 단계 실패를 덮지 않는다. reporter를 읽지 못하거나 필수 시험 집합을 결정할 수 없으면 미확인으로 막고 먼저 프로젝트의 출력 변환을 준비한다.

- `contract.json`: 실행 전 조정자가 고정한 계약. bytes의 SHA256을 state와 실행 spec에 저장한다. 구성원·명령·환경·필수 시험을 바꾸면 새 attempt를 만든다.
- 단계별 원본 로그와 `result.json`: runner가 수집한 결과. 종료 시 임시 파일을 완성한 뒤 같은 디렉터리에서 원자적으로 `result.json`으로 게시한다. 미완료 결과는 통과할 수 없다. attempt 경로를 재사용하지 않는다.

계약 형식은 다음과 같다. SHA는 축약하지 않은 실제 값이며 `stages`에는 전체 테스트·타입 검사·빌드 등 프로젝트가 요구하는 단계를 빠짐없이 넣는다. 환경이 없으면 `required_environment`는 빈 배열이다. 빌드 단계나 명시적으로 시험이 없는 scaffold 단계만 `required_tests`를 비울 수 있다.

계약의 추가 필드로 실행 명령의 식별 해시, 입력·의존성·런타임·옵션·비밀이 아닌 환경 버전도 기록한다. runner는 실제 실행 설정이 이 계약과 같은지 확인한다. 검증기는 이 추가 필드의 해시 결합까지만 확인하므로, qa의 동일성 확인을 대신하지 않는다.

```json
{
  "schema_version": 1,
  "attempt_id": "gate-<고유 ID>",
  "base_sha": "<전체 SHA>",
  "candidate_sha": "<전체 SHA>",
  "member_shas": ["<검토한 구성원 전체 SHA>"],
  "required_environment": ["database-ready", "browser-ready"],
  "stages": [
    {"id": "test", "required_tests": ["api/auth/denied", "browser/login"]},
    {"id": "build", "required_tests": []}
  ]
}
```

`result.json`은 같은 `schema_version`, `attempt_id`, `base_sha`, `candidate_sha`, `member_shas`와 `contract_sha256`을 담는다. `completed`, `clean_start`, `clean_end`는 실제 확인한 boolean이며 `head_start`, `head_end`는 후보 SHA다. `environment`는 위 조건 ID별 실제 사전 확인 결과(boolean)다. 각 stage 결과는 다음 형식이다. 필수 시험뿐 아니라 reporter가 내놓은 시험 결과 전부를 담는다.

```json
{
  "id": "test",
  "completed": true,
  "exit_code": 0,
  "tests": [{"id": "api/auth/denied", "status": "passed"}],
  "log_path": "test.log",
  "log_sha256": "<해당 로그 bytes의 SHA256>"
}
```

시험 status는 `passed`, `failed`, `skipped`, `cancelled` 중 하나다. 위 조각은 형식 설명이며 다른 필수 시험이 빠져 있으면 통과하지 않는다. 실측 시작·종료 시각과 대기·실행 시간은 runner 결과의 추가 필드로 남긴다. 자격 증명·연결 문자열은 결과와 로그에서 제외한다.

```text
python <스킬 경로>/scripts/check-gate.py <attempt>/contract.json <attempt>/result.json --contract-sha256 <state에 고정한 SHA256>
```

검증기 exit 0과 `status: passed`가 있어야 통과다. 검증기는 계약 해시, 실행·커밋 동일성, 단계 집합, 실제 exit, 필수 시험, 로그 무결성을 검사한다. 누락·형식 오류·대상 불일치는 통과하지 못한다. checker는 시험을 실행하거나 로그를 해석하는 reporter, OS 잠금, 승격 도구가 아니다. 조정자는 runner의 수집 경로와 실제 후보를 따로 확인해야 한다. 승인 상태는 이 판정에서만 파생하며 `known_env` 이름 차감이나 사용자 승인 목록으로 필수 gate를 통과 처리하지 않는다.

## 중복 실행과 적용 경계

검토자는 변경에 필요한 Acceptance를 직접 실행한다. 전체 suite를 다시 돌리는 부분만 동일 후보의 통합 gate로 맡길 수 있으며, spec·리포트에 위임한 필수 시험과 gate attempt를 연결한다. 검토 완료와 시험 완료를 구분한다. qa는 마지막 전체 gate가 **동일 후보·계약·입력·환경·런타임·옵션**이고 원본 로그가 보존됐으면 검증기로 재확인해 재사용한다. 하나라도 달라지거나 환경을 바꾼 qa라면 다시 실행한다. 단순히 이전 요약이나 tests 수가 같다는 이유로 재사용하지 않는다. 요구사항별 실제 PG·브라우저·실사본·결정성·메모리 시험을 생략하지 않는다.

추출물 캐시는 자동 도입하지 않는다. 원천·생산자 코드·런타임·옵션과 무결성 확인이 구현되고 실측 이득이 있을 때 별도 적용한다. 최종 신규 추출·결정성·메모리 검증은 기존 추출물로 우회하지 않는다.

새 Run은 `gate_protocol: 2`를 state에 기록한다. 이전 Run의 진행 중인 attempt는 기존 절차로 끝내며 기록을 새 형식으로 꾸미지 않는다. 복구 중 전환은 진행 중인 gate가 정리된 다음 새 attempt부터 하고, 이전 결과와 구분해 버전·적용 시점을 log에 남긴다. 기존 'passed(known_env...)'는 새 프로토콜의 통과 증거가 아니다.

적용 전 검증기의 회귀 검사와 과거 로그·상태의 불일치 확인을 한다. 이후 같은 코드·시험·입력·자원 조건에서 gate 실행·대기·재시도 시간과 전체 완료시간을 구분해 비교한다. 제품 성능 수용 기준과 필수 검증은 그대로 유지한다. 비교 조건이나 측정이 없으면 속도 향상률·무회귀를 입증했다고 보고하지 않는다.
