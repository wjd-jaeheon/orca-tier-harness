# spec: 할 일 API

## 목표
메모리 저장소 위의 할 일(todo) REST API.

## 동작
- R1. `POST /todos` 는 `{title}`을 받아 `{id,title,done:false}`를 201로 돌려준다. title이 비면 400.
- R2. `GET /todos` 는 전체 목록을 200으로 돌려준다.
- R3. `PATCH /todos/:id` 는 `done`을 바꾼다. 없는 id면 404.

## 불변 조건
- id는 서버가 부여하고 재사용하지 않는다.

## 검증
- `npm test`
