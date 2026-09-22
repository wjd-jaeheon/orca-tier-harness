# handoff

## Document roles
- spec.md: 동작의 기준. plan과 충돌하면 spec이 이긴다.
- plan.md: 작업 단위와 순서. 실행 그래프는 plan 안의 yaml 블록이다.

## Hard gates
- `npm test`가 exit 0이어야 한다.
- 외부 네트워크 호출을 추가하지 않는다.

## Execution shape
- 3개 Task. T1이 기반이고 T2, T3가 T1에 의존한다.
