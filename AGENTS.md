# AGENTS.md — slot-flow 작업 규칙

## 작업 전
- PRD.md · ARCHITECTURE.md · DECISIONS.md 를 읽는다.
- 계획을 보여 준 뒤 승인받고 나서 작업한다.

## 변경 범위
- main 에서 직접 작업하지 않는다. 브랜치를 만들어 작업한다.
- 이슈 하나씩 바꾼다.
- 삭제와 패키지 설치는 그때마다 다시 승인받는다.
- PRD 밖 기능을 제안받으면 구현하지 말고 DECISIONS.md 의 보류 목록 후보로만 보고한다.

## 완료 확인
- 바꾼 파일 · 명령 · 결과를 나누어 보고한다.
- 테스트가 실패하면 멈춘다.
- API 키 · 비밀번호는 Git 에 넣지 않는다.
- 커밋 메시지는 임의로 넣지 않고, 사용자가 직접 정한 메시지로 커밋한다.

## 문서 상태
- 문서 맨 위에 `- 상태:`로 적고, 값은 둘 중 하나다.
  - 초안: 뼈대를 작성하는 중이다.
  - 확정: 뼈대가 완성됐다. 프로젝트 동안 계속 갱신하며, 바꿀 때는 별도 결정이 필요하다.
- 적용 대상: PRD · DECISIONS · ARCHITECTURE · USER-WORKFLOW · SCREEN-SPEC · API-SPEC · DATA-MODEL · SCENARIO-REVIEW · BUSINESS-RULE-REVIEW · BUG. 그 밖의 문서(README · AGENTS · DEV-ENVIRONMENT · PRODUCT-DIRECTION · PROJECT-DISCOVERY)는 대상이 아니다.
- 확정 문서라도 기록 칸을 채우는 것은 변경으로 보지 않는다. 기록 칸은 REVIEW 문서의 실제결과 · 판정 · 검수 회차, BUG의 버그 행, DECISIONS의 보류 목록이다.
