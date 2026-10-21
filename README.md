# slot-flow

설정형 예약 웹 도구. 설계 문서: `PRD.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `USER-WORKFLOW.md`, `SCREEN-SPEC.md`, `API-SPEC.md`, `DATA-MODEL.md`.
현재는 M0(프로젝트 기본 구조)만 있으며 기능은 없다.

## 구조
- `backend/` — FastAPI. `app/routes`(API 진입부), `app/validation`(공통 검증), `app/services`(서비스), `app/storage`(저장소)는 비어 있다.
- `frontend/` — React · Vite. 개발 서버가 `/api/*`를 백엔드(8000)로 넘긴다.

## 실행
백엔드:
```
cd backend
uv run uvicorn app.main:app --reload
```
프론트엔드(다른 터미널):
```
cd frontend
npm install
npm run dev
```
http://localhost:5173 에서 "서버 상태: ok"가 보이면 연결된 것이다.
