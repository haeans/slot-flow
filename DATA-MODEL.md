- 상태: 확정

# DATA-MODEL — 설정형 예약 웹 도구 (slot-flow)

근거 문서: `PRD.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `API-SPEC.md`, `SCREEN-SPEC.md`, `USER-WORKFLOW.md`, `DATA-MIGRATION-PLAN.md`. US-xxx, Q-xxx, D-xxx, C-x(공통 검증 ID)는 이 문서들의 ID를 그대로 쓴다.
ARCHITECTURE 4절의 논리적 저장 구조를 SQLite 테이블 수준(컬럼, 타입, 제약, 인덱스)으로 구체화한다.
아직 정해지지 않은 것은 **[결정 필요 Q-xx]**로 표시하고 이 문서에서 정하지 않는다. PRD에 Q-ID가 없는 항목은 **[결정 필요: PRD에 없음]**으로 표시한다.
이 문서를 쓰면서 정한 것은 8절에 모았고, `DECISIONS.md`의 D-029~D-036으로 기록했다.

---

## 1. 개요

| 테이블 | 담는 것 | ARCHITECTURE 4절 |
|---|---|---|
| `resources` | 자원 이름, 최소·최대 이용시간, 취소 마감 | 자원 |
| `operating_hours` | 자원의 요일별 운영시간 (요일마다 한 행) | 자원 (운영시간) |
| `reservations` | 예약 한 건 | 예약 |
| `accounts` | 관리자·운영자·회원 고객 계정 | 계정 |
| `sessions` | 로그인 세션 (토큰의 HMAC 값만) | 계정 (세션) |
| `login_failures` | 이메일별 연속 로그인 실패와 잠금 | 계정 (로그인 시도 제한) |

- 모든 테이블은 `STRICT` 테이블로 만든다. 선언한 타입과 다른 값은 저장소가 거부한다. (D-029)
- 테이블은 여섯이다(D-057, D-062). 계정·세션·로그인 실패는 2.4~2.6절이다. 구조를 만들고 바꾸는 절차는 `DATA-MIGRATION-PLAN.md` 5절(절차 0001~0004)이다. (D-064)
- 저장소의 CHECK 제약은 최후 방어다. 판정은 API의 입력 형식 검사와 공통 검증이 먼저 한다(D-002, D-036). 그런데도 CHECK에 걸리면 판정이 빠진 버그로 보고 `STORAGE_ERROR`(500)로 응답한다. 겹침 트리거는 예외로, 저장 단계의 최종 보장(D-003)이며 `OVERLAP`(409)으로 응답한다. (3절)
- 모든 연결에서 아래를 설정한다. (D-032)
  | 설정 | 값 | 이유 |
  |---|---|---|
  | `PRAGMA foreign_keys` | `ON` | SQLite는 외래키 검사를 연결마다 켜야 한다 |
  | `PRAGMA busy_timeout` | `5000` (밀리초) | 다른 쓰기가 끝날 때까지 기다린다. 초과하면 `STORAGE_ERROR`(500) |
  | `PRAGMA journal_mode` | `WAL` | 쓰는 동안에도 읽기가 막히지 않는다 |
- DB 파일은 `backend/data/slot-flow.db`이다. 서버를 시작할 때 alembic 절차(`backend/migrations`)를 최신까지 적용하고, DB 파일이 없으면 새로 만든다. DB 파일은 Git에 넣지 않는다. (D-034, D-064, `DATA-MIGRATION-PLAN.md` 5절)

## 2. 테이블

### 2.1 `resources` — 자원
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `id` | INTEGER | 불가 | 자동 증가 | PK | — | API-SPEC 6절 |
| `name` | TEXT | 불가 | — | — | 길이·빈 값·중복 **[결정 필요: PRD에 없음]** | US-001 |
| `min_duration_minutes` | INTEGER | 불가 | — | — | `> 0`, `% 30 = 0` | D-018, D-029 |
| `max_duration_minutes` | INTEGER | 불가 | — | — | `> 0`, `% 30 = 0`, `min_duration_minutes <= max_duration_minutes` | D-018, D-029, D-036 |
| `cancel_deadline_hours` | INTEGER | 불가 | — | — | 범위(0 허용 여부, 상한) **[결정 필요: PRD에 없음]** | D-012 |
| `owner_account_id` | INTEGER | 불가 | — | FK → `accounts.id` | — | D-044, D-057 |

- 이름 외 자원 정보: **[결정 필요 Q-15]**
- 자원 삭제·숨김은 두지 않는다. 그래서 외래키의 삭제 동작(`ON DELETE`)도 정하지 않는다. **[결정 필요 Q-15]**
- **소유 운영자**: 자원을 등록한 운영자의 계정이다. 운영자 소유 확인(C-9)이 이 컬럼을 쓴다. 이 계정이 `role = 'operator'`인지는 저장소가 아니라 API 진입 단계의 역할 검사(C-5)가 보장한다. (D-044)
- 고객이 예약할 수 있는 자원은 소유 운영자가 `approved`인 자원뿐이다. 정지된 운영자의 자원은 새 예약을 받지 않는다. (D-065)

### 2.2 `operating_hours` — 요일별 운영시간
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `resource_id` | INTEGER | 불가 | — | PK, FK → `resources.id` | — | D-019 |
| `weekday` | TEXT | 불가 | — | PK | `IN ('mon','tue','wed','thu','fri','sat','sun')` | D-019, API-SPEC 1.2 |
| `open_time` | TEXT | 불가 | — | — | `HH:MM`, 30분 단위, `00:00`~`23:30` (4.2) | D-019, D-031 |
| `close_time` | TEXT | 불가 | — | — | `open_time`과 같음. `open_time < close_time` | D-019, D-031, D-036 |

- 기본키 `(resource_id, weekday)`로 요일마다 한 구간만 둔다. (D-019)
- 운영하지 않는 요일은 행이 없다. API에서는 그 요일의 값이 `null`이다. (API-SPEC 4절)
- 자원 수정(`PUT`)은 모든 필드를 한 번에 바꾸므로, 같은 쓰기 단위 안에서 그 자원의 운영시간 행을 모두 지우고 다시 넣는다. (API-SPEC 4.4)

### 2.3 `reservations` — 예약
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `id` | INTEGER | 불가 | 자동 증가 | PK | — | D-029 (내부 키, API에 내보내지 않음) |
| `reservation_code` | TEXT | 불가 | — | UNIQUE | 형식 (4.3) | D-045, D-033 |
| `resource_id` | INTEGER | 불가 | — | FK → `resources.id` | — | D-021 |
| `start_at` | TEXT | 불가 | — | — | 시각 형식 (4.1) | D-022, D-030 |
| `end_at` | TEXT | 불가 | — | — | 시각 형식 (4.1), `start_at < end_at` | D-022, D-030 |
| `status` | TEXT | 불가 | `'reserved'` | — | `IN ('reserved','cancelled')` | F-12, D-004 |
| `customer_name` | TEXT | 불가 | — | — | 길이·빈 값 **[결정 필요: PRD에 없음]** | D-021, D-068 |
| `customer_account_id` | INTEGER | 가능 | `NULL` | FK → `accounts.id` | — | D-045, D-057 |

- 취소는 행을 지우지 않고 `status`를 `cancelled`로 바꾼다. (D-004) 취소는 되돌리지 않는다. 이 상태 전이 판정(C-7)은 공통 검증이 하고 저장소는 하지 않는다. (ARCHITECTURE 5절)
- 예약에 담는 항목은 위가 전부다. (D-021) 생성 시각·취소 시각은 담지 않는다. 확장 1의 통계(R-016)에 필요할 수 있어 제안만 해 둔다. (9절)
- **회원 계정**: 회원 예약이면 그 회원의 계정이고, 비회원 예약이면 `NULL`이다. 운영자·관리자 세션으로 만든 예약도 `NULL`이다. 겹침 판정(3절)은 이 컬럼을 보지 않는다. (D-045, D-061)
- 회원이 이름을 생략하면 `customer_name`에 계정 이름을 저장한다. (D-068) 비회원 예약은 나중에 계정에 연결하지 않는다. (D-069)

### 2.4 `accounts` — 계정
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `id` | INTEGER | 불가 | 자동 증가 | PK | — | 내부 키, API에 내보내지 않음 |
| `email` | TEXT | 불가 | — | UNIQUE | `email = lower(email)`, `length(email) BETWEEN 3 AND 254`, `instr(email, '@') > 1` | D-056 |
| `password_hash` | TEXT | 불가 | — | — | `password_hash GLOB '$argon2id$*'` | D-063 |
| `name` | TEXT | 불가 | — | — | `name = trim(name)`, `length(name) BETWEEN 1 AND 50` | D-059 |
| `role` | TEXT | 불가 | — | — | `IN ('admin','operator','customer')` | D-042 |
| `operator_status` | TEXT | 가능 | — | — | `role = 'operator'`이면 `IN ('pending','approved','suspended')`, 아니면 `NULL` | D-043, D-053 |
| `booking_slug` | TEXT | 가능 | — | UNIQUE | `role = 'operator'`이면 필수, 아니면 `NULL`. 영문 소문자·숫자·`-` 3~30자, `-`로 시작하거나 끝나지 않음 | D-046, D-059 |
| `created_at` | TEXT | 불가 | — | — | 시각 형식 (4.4) | 운영자 목록의 정렬 (D-067) |

- 관리자는 1명이다. 부분 유일 인덱스 `UNIQUE (role) WHERE role = 'admin'`이 두 번째 관리자를 막는다. (D-050)
- 이메일은 API가 앞뒤 공백을 지우고 소문자로 바꾼 뒤 저장·비교한다. (D-056)
- 비밀번호 값은 `pwdlib`이 만든 문자열이다. 알고리즘·설정·salt가 함께 들어 있어 salt 컬럼을 따로 두지 않는다. (D-063)
- 운영자는 가입하면 `pending`이고, 관리자가 `approved` 또는 `suspended`로 바꾼다. 정지된 운영자는 다시 승인하지 않는다. (D-043, D-067)
- 계정 삭제는 두지 않는다. 그래서 외래키의 삭제 동작(`ON DELETE`)도 정하지 않는다. **[결정 필요: PRD에 없음]**

### 2.5 `sessions` — 로그인 세션
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `token_hash` | TEXT | 불가 | — | PK | `length = 64`, 소문자 16진수 | D-049 |
| `account_id` | INTEGER | 불가 | — | FK → `accounts.id` | — | D-049 |
| `created_at` | TEXT | 불가 | — | — | 시각 형식 (4.4) | D-049 |
| `expires_at` | TEXT | 불가 | — | — | 시각 형식 (4.4), `created_at < expires_at` | D-049 (7일) |

- `token_hash`는 `HMAC-SHA256(SLOTFLOW_SESSION_SECRET, 토큰 원문)`이다. 토큰 원문과 비밀값은 저장하지 않는다. (D-049)
- 만료된 행은 요청 때 지운다. 로그아웃하면 그 행을, 운영자를 정지하거나 비밀번호를 재설정하면 그 계정의 행을 모두 지운다. (D-049, D-053, D-059)

### 2.6 `login_failures` — 로그인 실패 기록
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `email` | TEXT | 불가 | — | PK | `email = lower(email)` | D-062 |
| `failed_count` | INTEGER | 불가 | — | — | `BETWEEN 1 AND 5` | D-062 |
| `last_failed_at` | TEXT | 불가 | — | — | 시각 형식 (4.4) | D-062 |
| `locked_until` | TEXT | 가능 | `NULL` | — | 시각 형식 (4.4). `failed_count = 5`일 때만 값이 있음 | D-062 |

- 계정이 없는 이메일도 똑같이 기록하므로 `accounts`를 외래키로 가리키지 않는다. (D-054, D-062)
- 로그인에 성공하거나 비밀번호를 재설정하면 그 이메일의 행을 지운다. 잠금이 풀린 뒤의 실패는 1번부터 다시 센다. (D-062)

## 3. 겹침 보장 (D-003, D-032, D-035)

같은 자원에서 시간이 겹치는 `reserved` 예약은 저장될 수 없다. 두 가지를 함께 쓴다.

**쓰기 단위**: 쓰는 요청(자원 등록·수정, 예약 생성·취소)은 입력 형식 검사 뒤, 저장소를 읽는 첫 판정 전에 `BEGIN IMMEDIATE`로 쓰기 단위를 시작한다. 저장소를 읽는 판정과 저장은 모두 그 안에서 한다. SQLite는 쓰기를 한 번에 하나만 받으므로, 동시에 들어온 요청은 차례로 처리되고 판정 중에 자원 규칙이나 예약 상태가 바뀌지 않는다. 실패하거나 거부되면 쓰기 단위 전체를 되돌린다.

**트리거**: 겹침 판정의 최종 보장은 트리거가 한다. 서비스 코드가 검사를 빠뜨려도 저장소가 막는다.

| 트리거 | 언제 | 거부 조건 | 동작 |
|---|---|---|---|
| 생성 시 겹침 거부 | `reservations`에 INSERT 전, 새 행의 `status`가 `reserved`일 때 | 같은 `resource_id`에 `status = 'reserved'`이고 `기존.start_at < 새.end_at AND 새.start_at < 기존.end_at`인 행이 있음 | `RAISE(ABORT, 'OVERLAP')` |
| 변경 시 겹침 거부 | `resource_id`, `start_at`, `end_at`, `status` UPDATE 전, 새 값의 `status`가 `reserved`일 때 | 위와 같고, 자기 자신(`기존.id <> 새.id`)은 제외 | `RAISE(ABORT, 'OVERLAP')` |

- 부등호가 엄격하므로 앞 예약의 끝과 뒤 예약의 시작이 같으면 겹침이 아니다. (D-009)
- `cancelled` 예약은 비교하지 않는다. 취소한 시간대는 곧바로 다시 예약할 수 있다. (D-010)
- 트리거가 거부하면 SQLite가 제약 위반 오류를 낸다. 서비스는 메시지가 `OVERLAP`인 이 오류를 `409 OVERLAP`으로 응답한다. 그 밖의 저장소 오류는 `500 STORAGE_ERROR`다. (API-SPEC 1.6)
- 예약 생성: 입력 형식 → 쓰기 단위 시작 → 자원 존재 → 지나간 시각 → C-1 → C-2 → INSERT(트리거가 C-3 판정) → 쓰기 단위 끝. 판정 순서는 D-028 그대로이고, 겹침은 마지막이다. (API-SPEC 5.1)
- 예약 취소: 쓰기 단위 시작 → C-8 → C-7 → C-4 → `status` 변경 → 쓰기 단위 끝. (API-SPEC 5.3)
- 자원 수정: 입력 형식 → 쓰기 단위 시작 → 자원 존재 → 자원 행 변경, 운영시간 행 교체 → 쓰기 단위 끝. (API-SPEC 4.4)

## 4. 값의 저장 형식

### 4.1 시각 (D-022, D-027, D-030)
- API의 형식 그대로 TEXT로 저장한다: `YYYY-MM-DDTHH:MM:SS+09:00` (고정 25자). 예: `2026-10-21T10:00:00+09:00`
- 저장소의 형식 검사: `GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[03]0:00+09:00'`. 분은 `00` 또는 `30`, 초는 `00`만 허용한다. (D-018) 실제로 있는 날짜인지는 API의 입력 형식 검사가 확인한다.
- 오프셋과 길이가 모두 같으므로, 문자열 비교 순서가 곧 시간 순서다. 겹침 판정(3절)과 범위 조회(5절)는 문자열 비교로 한다.
- 예약은 하루 안에서 끝난다. 운영시간이 `23:30`을 넘지 않기 때문이다. (4.2)

### 4.2 운영시간의 시각 (D-019, D-031)
- `HH:MM` TEXT로 저장한다. 30분 단위(`:00` 또는 `:30`)만 허용한다. 30분 칸(D-020)으로 나누기 위해서다.
- 범위는 `00:00`~`23:30`이다. 자정 종료(`24:00`)는 첫 버전에서 허용하지 않는다.
- 저장소의 형식 검사: `GLOB '[0-2][0-9]:[03]0'`이고 앞 두 자리가 `'23'` 이하.

### 4.3 예약 코드 (D-033, D-045, Q-21)
| 항목 | 값 |
|---|---|
| 길이 | 10자 |
| 문자 | `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (31자. 헷갈리는 `0` `O` `1` `I` `L` 제외) |
| 생성 | 서버가 Python 표준 라이브러리 `secrets`로 무작위 생성. 패키지 설치 없음 (D-001) |
| 경우의 수 | 31¹⁰ ≈ 8.2 × 10¹⁴ (약 49비트) |
| 중복 | `UNIQUE`. 생성한 코드가 이미 있으면 다시 생성한다 |
| 입력 비교 | 고객이 입력한 코드를 대문자로 바꿔 비교한다 |
| 저장소 검사 | `length = 10` 이고 위 31자 밖의 문자가 없음 |

### 4.4 계정·세션의 시각
- 예약 시각(4.1)과 같은 `YYYY-MM-DDTHH:MM:SS+09:00` 고정 25자 TEXT지만 30분 단위 제한이 없고 초까지 쓴다.
- 저장소의 형식 검사: `GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]+09:00'`
- 만료·잠금 판정은 문자열 비교로 한다. (4.1과 같은 이유)

## 5. 인덱스

| 인덱스 | 대상 | 쓰는 곳 |
|---|---|---|
| `reservations(resource_id, start_at)` | 예약 | 겹침 판정(3절), 날짜별 칸 조회(API-SPEC 4.2), 운영자 예약 목록의 자원·날짜 필터(API-SPEC 5.4) |
| `reservations(reservation_code)` | 예약 | `UNIQUE` 제약이 만드는 인덱스. 내 예약 조회·취소 (API-SPEC 5.2, 5.3) |
| `operating_hours(resource_id, weekday)` | 운영시간 | 기본키가 만드는 인덱스. 운영시간 판정(C-1), 칸 계산 |
| `resources(owner_account_id)` | 자원 | 운영자의 자기 자원 목록, 소유 확인(C-9) |
| `reservations(customer_account_id)` | 예약 | 회원의 내 예약 목록 (D-068) |
| `accounts(email)`, `accounts(booking_slug)` | 계정 | `UNIQUE` 제약이 만드는 인덱스. 로그인, 예약 주소 조회, 운영자 승인·정지 |
| `accounts(role) WHERE role = 'admin'` | 계정 | 부분 유일 인덱스. 관리자 1명 (D-050) |
| `sessions(token_hash)`, `sessions(account_id)` | 세션 | 기본키로 세션 확인, 계정별 세션 삭제 (D-053) |
| `login_failures(email)` | 로그인 실패 | 기본키가 만드는 인덱스. 잠금 확인 (D-062) |

- 날짜 필터는 `start_at >= '<날짜>T00:00:00+09:00' AND start_at < '<다음 날>T00:00:00+09:00'`로 비교한다. (4.1)
- 상태 필터(`status`)는 자원·날짜로 좁힌 뒤 거르므로 따로 인덱스를 두지 않는다.

## 6. 저장하지 않는 것

| 값 | 어디에 있나 | 근거 |
|---|---|---|
| 비밀번호 원문, 세션 토큰 원문 | 저장하지 않는다. 비밀번호는 argon2id 값, 세션은 `SLOTFLOW_SESSION_SECRET`을 키로 한 HMAC 값만 저장한다 | D-063, D-049 |
| 세션 비밀값 | `backend/.env`(Git 제외). 항목 이름만 `backend/.env.example`에 둔다 | D-049 |
| 날짜별 30분 칸(`slots`) | 요청 때 운영시간과 `reserved` 예약으로 계산 | D-020, API-SPEC 4.2 |
| 거부 사유(`error`) | 요청마다 만들어 응답 | D-006 |

## 7. 화면 · API · 데이터 짝 맞추기

| 화면 (SCREEN-SPEC) | API 필드 (API-SPEC) | 테이블.컬럼 | 형식·값 범위 | 근거 |
|---|---|---|---|---|
| 자원 선택 (자원 관리, 예약하기, 예약 목록 필터) | `id`, `resource_id` | `resources.id`, `reservations.resource_id` | INTEGER | API-SPEC 6절 |
| 자원 이름 입력·표시 (자원 관리, 예약하기, 내 예약) | `name`, `resource_name` | `resources.name` (내 예약은 조인) | TEXT, 길이 [결정 필요: PRD에 없음] | US-001 |
| 운영시간의 요일 (자원 관리) | `operating_hours`의 키 | `operating_hours.weekday` | `mon`~`sun` | D-019 |
| 운영시간 시작·종료 (자원 관리) | `operating_hours.{요일}.open` / `.close` | `operating_hours.open_time` / `close_time` | `HH:MM`, 30분 단위, `00:00`~`23:30` | D-019, D-031 |
| 운영하지 않는 요일 "비워 둠" (자원 관리) | `operating_hours.{요일}: null` | 행 없음 | — | D-019 |
| 최소·최대 이용시간 (자원 관리) | `min_duration_minutes`, `max_duration_minutes` | `resources` 같은 이름 | 30의 배수, `> 0` | D-018, D-029 |
| 취소 마감 N (자원 관리) | `cancel_deadline_hours` | `resources.cancel_deadline_hours` | 정수, 범위 [결정 필요: PRD에 없음] | D-012 |
| 날짜 선택 (예약하기) | `date` (쿼리) | 저장하지 않음 (요청 값) | `YYYY-MM-DD` | D-027 |
| 30분 칸 (예약하기) | `slots[].start_at`, `slots[].end_at` | 저장하지 않음 (`operating_hours`로 계산) | 시각 | D-020 |
| 칸의 "예약됨" (예약하기) | `slots[].status` | 저장하지 않음 (`reservations.status = 'reserved'`와의 겹침으로 계산) | `available` / `reserved` | D-020 |
| 시작·종료 시각 선택 (예약하기), 표시 (내 예약, 예약 목록) | `start_at`, `end_at` | `reservations.start_at`, `reservations.end_at` | `YYYY-MM-DDTHH:MM:SS+09:00` | D-027, D-030 |
| 고객 이름 입력 (예약하기), 표시 (내 예약, 예약 목록) | `customer_name` | `reservations.customer_name` | TEXT, 길이 [결정 필요: PRD에 없음] | D-021 |
| 상태 표시 (내 예약, 예약 목록), 상태 필터 (예약 목록) | `status` | `reservations.status` | `reserved` / `cancelled` | F-12, D-004 |
| 예약 코드 표시 (예약하기 성공), 입력·표시 (내 예약) | `reservation_code` | `reservations.reservation_code` | 4.3 | D-045, D-033 |
| 날짜 필터 (예약 목록) | `date` (쿼리) | `reservations.start_at` 범위 비교 | `YYYY-MM-DD` | D-013 |
| 거부 사유 표시 (모든 화면) | `error.code`, `error.message` | 저장하지 않음 | API-SPEC 1.6 | D-006 |
| 로그인·가입 입력 (로그인, 가입) | `email`, `password`, `name`, `role` | `accounts.email`, `accounts.password_hash`(argon2id 값), `accounts.name`, `accounts.role` | 이메일·비밀번호(8~128자)·이름(1~50자) | D-056, D-059 |
| 운영자 예약 주소명 (예약하기 진입, 가입) | `booking_slug`, `operator`(쿼리) | `accounts.booking_slug` | 영문 소문자·숫자·`-` 3~30자 | D-046, D-059 |
| 운영자 상태 (운영자 관리, 운영자 구역) | `operator_status` | `accounts.operator_status` | `pending` / `approved` / `suspended` | D-043, D-067 |
| 자원의 소유 운영자 (자원 관리) | 응답에 담지 않음 (세션의 운영자) | `resources.owner_account_id` | 계정 내부 키 | D-044 |
| 회원 예약 표시 (예약하기, 내 예약 목록) | `is_member` | `reservations.customer_account_id` | 비회원이면 `NULL` | D-045, D-068 |
| 로그인 상태 (모든 로그인 화면) | 쿠키 `slotflow_session` | `sessions.token_hash` (HMAC 값) | 7일 | D-049 |

짝 없음:
| 값 | 없는 쪽 | 이유 |
|---|---|---|
| `reservations.id` | API, 화면 | 내부 키다. 외부 식별자는 예약 코드다 (D-029) |
| 예약 목록의 예약 코드 | API, 화면 | 운영자에게 보여 줄지 **[결정 필요 Q-20]**. 컬럼은 있다 |
| 고객에게 보여 줄 이용 규칙 | API, 화면 | 범위 **[결정 필요 Q-17]**. 컬럼은 있다 |

## 8. 이 문서에서 정한 것

`DECISIONS.md`에 기록했다.

| D-ID | 정한 것 |
|---|---|
| D-029 | 테이블은 `resources`, `operating_hours`, `reservations`로 시작했고(D-057, D-062로 여섯) 모두 `STRICT`다. 예약은 예약 코드와 따로 내부 키 `id`를 둔다. 이용시간은 `> 0` |
| D-030 | 시각은 API 형식 그대로 고정 25자 TEXT로 저장하고 문자열로 비교한다 |
| D-031 | 운영시간의 시각은 `HH:MM`, 30분 단위, `00:00`~`23:30`. 자정 종료는 허용하지 않는다 |
| D-032 | 겹침은 `BEGIN IMMEDIATE` 쓰기 단위와 INSERT·UPDATE 트리거로 보장한다. 연결마다 `foreign_keys=ON`, `busy_timeout=5000`, `journal_mode=WAL` |
| D-033 | 예약 코드는 헷갈리는 문자를 뺀 31자 중 10자, `secrets`로 생성, `UNIQUE`, 입력은 대문자로 바꿔 비교 (Q-21) |
| D-034 | DB 파일은 `backend/data/slot-flow.db`, 서버 시작 때 테이블을 만들고(방법은 D-064), Git에 넣지 않는다 |
| D-035 | 쓰는 요청은 입력 형식 검사 뒤, 저장소를 읽는 첫 판정 전에 쓰기 단위를 시작한다 |
| D-036 | 자원 입력의 거부 기준: 30분 단위·범위, 최소 ≤ 최대, 열림 < 닫힘, 일곱 요일 키. 저장소 CHECK는 최후 방어 |

## 9. 결정 필요 모아 보기

원본은 `DECISIONS.md`의 "결정 필요 모아 보기"다. 이 문서에서는 따로 관리하지 않는다.
이 문서에 영향을 주는 열린 질문: Q-14(경계 시각, 저장 구조에는 영향 없음), Q-15, Q-22(휴무일·예외일 세부 규칙, 저장 구조에 영향), Q-17, Q-20, 자원 이름의 길이·빈 값·중복, 취소 마감 N의 범위, 고객 이름의 길이·빈 값, 생성·취소 시각 컬럼(제안)
