# plan

## T1 저장소와 서버 뼈대
- goal: 메모리 저장소 모듈과 express 앱 진입점.
- work targets: files: src/store.js, src/app.js
- verification gate: `npm test -- store`
- spec: 불변 조건(id 부여)

## T2 생성과 목록 엔드포인트
- goal: R1, R2 구현.
- work targets: files: src/routes/todos.js, test/todos.create.test.js
- verification gate: `npm test -- todos.create`
- spec: R1, R2

## T3 완료 표시 엔드포인트
- goal: R3 구현.
- work targets: files: src/routes/done.js, test/todos.done.test.js
- verification gate: `npm test -- todos.done`
- spec: R3

## shared-write
- src/app.js 의 라우트 등록은 T2, T3가 건드리지 않는다. wave 끝에 한 번에 등록한다.

```yaml
tasks:
  - id: T1
    depends: []
    risk: MECHANICAL
  - id: T2
    depends: [T1]
    risk: RISKY
  - id: T3
    depends: [T1]
    risk: RISKY
regen_barriers: []
```
