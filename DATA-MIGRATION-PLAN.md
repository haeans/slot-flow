# DATA-MIGRATION-PLAN — 로그인 기능의 저장 구조 변경 (slot-flow)

근거 문서: `PRD.md`, `DECISIONS.md`, `DATA-MODEL.md`, `API-SPEC.md`, `API-SPEC-CHANGE.md`. US-xxx, Q-xxx, D-xxx, C-x는 이 문서들의 ID를 그대로 쓴다.
PRD Must의 R-018~R-023(계정·로그인)을 위해 저장 구조를 바꾸는 계획이다. 결정은 D-055~D-057, D-059, D-062다.
아직 정해지지 않은 것은 **[결정 필요 Q-xx]** 또는 **[결정 필요: PRD에 없음]**으로 표시하고 이 문서에서 정하지 않는다.

---

## 1. 바뀌는 것 한눈에

| 테이블 | 변경 | 내용 | 근거 |
|---|---|---|---|
| `accounts` | 새로 만듦 | 관리자·운영자·회원 고객 계정 | D-042, D-043, D-055, D-056 |
| `sessions` | 새로 만듦 | 로그인 세션 (토큰의 HMAC 값만) | D-049, D-053 |
| `login_failures` | 새로 만듦 | 이메일별 연속 로그인 실패와 잠금 | D-062 |
| `resources` | 컬럼 추가 | `owner_account_id` (필수) | D-044 |
| `reservations` | 컬럼 추가 | `customer_account_id` (회원 예약만) | D-045 |
| `operating_hours` | 변경 없음 | — | — |

- 테이블은 셋에서 여섯이 된다. 모든 테이블은 그대로 `STRICT`다. (D-029, D-057)
- 연결 설정(`foreign_keys=ON`, `busy_timeout=5000`, `journal_mode=WAL`)은 그대로다. (D-032)
- 기존 DB 파일은 지우고 새로 만든다. 기존 데이터는 옮기지 않는다. (D-057, 5절)

## 2. 새 테이블

### 2.1 `accounts` — 계정
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `id` | INTEGER | 불가 | 자동 증가 | PK | — | 내부 키, API에 내보내지 않음 |
| `email` | TEXT | 불가 | — | UNIQUE | `email = lower(email)`, `length(email) BETWEEN 3 AND 254`, `instr(email, '@') > 1` | D-056 |
| `password_hash` | TEXT | 불가 | — | — | `password_hash GLOB '$argon2id$*'` | D-055 |
| `name` | TEXT | 불가 | — | — | `name = trim(name)`, `length(name) BETWEEN 1 AND 50` | D-059 |
| `role` | TEXT | 불가 | — | — | `IN ('admin','operator','customer')` | D-042 |
| `operator_status` | TEXT | 가능 | — | — | `role = 'operator'`이면 `IN ('pending','approved','suspended')`, 아니면 `NULL` | D-043, D-053 |
| `booking_slug` | TEXT | 가능 | — | UNIQUE | `role = 'operator'`이면 필수, 아니면 `NULL`. `length BETWEEN 3 AND 30`, `NOT GLOB '*[^a-z0-9-]*'`, `NOT GLOB '-*'`, `NOT GLOB '*-'` | D-046, D-059 |
| `created_at` | TEXT | 불가 | — | — | 시각 형식 (4절) | 운영자 목록의 정렬 (API-SPEC 2절 #13) |

- **관리자는 1명**: 부분 유일 인덱스 `UNIQUE (role) WHERE role = 'admin'`로 저장소가 두 번째 관리자를 막는다. (D-050)
- **이메일**: API가 앞뒤 공백을 지우고 소문자로 바꾼 뒤 저장·비교한다. CHECK는 최후 방어다. 형식 검사의 자세한 기준은 API-SPEC-CHANGE 2.1에 있다. (D-036과 같은 원칙)
- **비밀번호 값**: `argon2-cffi`가 만든 문자열을 그대로 저장한다. 그 안에 알고리즘, 설정값, salt가 들어 있어 salt 컬럼을 따로 두지 않는다. 예: `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>` (D-055)
- **운영자 상태**: 가입하면 `pending`이 되고, 관리자가 `approved` 또는 `suspended`로 바꾼다. (D-043)
- **예약 주소명**: 운영자의 고객 예약 주소 `/r/{booking_slug}`에 쓴다(D-046). 고객의 자원 목록 조회가 이 컬럼으로 운영자를 찾는다(API-SPEC-CHANGE 3절). 주소명을 나중에 바꿀 수 있는지: **[결정 필요: PRD에 없음]**
- **비밀번호 재설정**: 관리자가 서버 명령으로 `password_hash`를 바꾸고, 그 계정의 `sessions`와 `login_failures` 행을 지운다. (D-059)
- 계정 삭제는 두지 않는다. 그래서 외래키의 삭제 동작(`ON DELETE`)도 정하지 않는다. **[결정 필요: PRD에 없음]**

### 2.2 `sessions` — 로그인 세션
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `token_hash` | TEXT | 불가 | — | PK | `length = 64`, 소문자 16진수 | D-049 |
| `account_id` | INTEGER | 불가 | — | FK → `accounts.id` | — | D-049 |
| `created_at` | TEXT | 불가 | — | — | 시각 형식 (4절) | D-049 |
| `expires_at` | TEXT | 불가 | — | — | 시각 형식 (4절), `created_at < expires_at` | D-049 (7일) |

- `token_hash`는 `HMAC-SHA256(SLOTFLOW_SESSION_SECRET, 토큰 원문)`의 16진수 값이다. 토큰 원문과 비밀값은 저장하지 않는다. (D-049, 6절)
- `expires_at`은 `created_at` + 7일이다. 요청 때 `expires_at <= 지금`이면 무효로 보고 그 행을 지운다.
- 로그아웃하면 그 행을, 관리자가 운영자를 정지하면 그 운영자의 행을 모두 지운다. (D-049, D-053)
- 인덱스 `sessions(account_id)`: 정지할 때 그 운영자의 세션을 한꺼번에 지우는 데 쓴다.

### 2.3 `login_failures` — 로그인 실패 기록
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `email` | TEXT | 불가 | — | PK | `email = lower(email)` | D-062 |
| `failed_count` | INTEGER | 불가 | — | — | `BETWEEN 1 AND 5` | D-062 |
| `last_failed_at` | TEXT | 불가 | — | — | 시각 형식 (4절) | D-062 |
| `locked_until` | TEXT | 가능 | `NULL` | — | 시각 형식 (4절). `failed_count = 5`일 때만 값이 있음 | D-062 |

- `accounts`를 외래키로 가리키지 않는다. 계정이 없는 이메일도 똑같이 기록해야, 잠금 응답으로 계정이 있는지 알 수 없다. (D-054, D-062)
- 실패하면 쓰기 단위 안에서 `failed_count`를 1 올린다. 5가 되면 `locked_until` = 지금 + 10분이다. `locked_until`이 지난 뒤 실패하면 `failed_count = 1`, `locked_until = NULL`로 다시 시작한다.
- 로그인에 성공하거나 비밀번호를 재설정하면 그 이메일의 행을 지운다.
- 행이 쌓이지 않도록, 로그인 요청 때 `last_failed_at`이 하루보다 오래됐고 잠기지 않은 행을 지운다. (이 문서에서 정함)

## 3. 기존 테이블에 더하는 컬럼

### 3.1 `resources`
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `owner_account_id` | INTEGER | 불가 | — | FK → `accounts.id` | — | D-044 |

- 자원을 등록한 운영자의 계정이다. 운영자 소유 확인(C-9)이 이 컬럼을 쓴다.
- 이 계정이 `role = 'operator'`인지는 저장소가 아니라 API 진입 단계의 역할 검사(C-5)가 보장한다. 외래키는 다른 테이블의 값을 CHECK할 수 없다.
- 인덱스 `resources(owner_account_id)`: 운영자의 자원 목록 조회(API-SPEC 4.1)에 쓴다.

### 3.2 `reservations`
| 컬럼 | 타입 | NULL | 기본값 | 키 | 제약 | 근거 |
|---|---|---|---|---|---|---|
| `customer_account_id` | INTEGER | 가능 | `NULL` | FK → `accounts.id` | — | D-045, D-051 |

- 회원 예약이면 그 회원의 계정이고, 비회원 예약이면 `NULL`이다.
- 겹침 트리거(DATA-MODEL 3절)는 이 컬럼을 보지 않는다. 트리거는 바꾸지 않는다.
- 인덱스 `reservations(customer_account_id)`: 회원의 내 예약 목록(API-SPEC 2절 #15)에 쓴다.
- 비회원 예약을 나중에 계정에 연결할지: **[결정 필요 Q-26]**

## 4. 값의 저장 형식

| 값 | 형식 | 비고 |
|---|---|---|
| 계정·세션의 시각 (`created_at`, `expires_at`) | `YYYY-MM-DDTHH:MM:SS+09:00` 고정 25자 TEXT | 예약 시각(D-030)과 같은 형식이지만 30분 단위 제한은 없다. 초까지 쓴다. 오프셋과 길이가 같아 만료 비교는 문자열 비교로 한다. GLOB: `'[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]+09:00'` |
| 세션 토큰 원문 | `secrets.token_urlsafe(32)` (쿠키에만) | 저장하지 않는다 |
| `token_hash` | HMAC-SHA256 16진수 64자 | 2.2 |
| 이메일 | 소문자, 3~254자 | D-056 |

## 5. 이전 절차

### 5.1 방식
기존 DB를 지우고 새 구조로 만든다. (D-057)

| 검토한 방식 | 결과 | 이유 |
|---|---|---|
| `ALTER TABLE … ADD COLUMN` | 쓰지 않음 | `owner_account_id`는 기본값 없는 `NOT NULL` 외래키다. SQLite는 행이 있는 테이블에 이런 컬럼을 더할 수 없다 |
| 새 테이블을 만들고 기존 행을 옮김 | 쓰지 않음 | 기존 자원의 주인이 될 운영자가 없다. 기존 데이터는 개발용이다 |
| **DB 파일을 지우고 새로 만듦** | **채택** | 사용자 결정(2026-10-22). 가장 단순하고, 옛 구조가 남지 않는다 |

### 5.2 순서
| # | 할 일 | 확인 |
|---|---|---|
| 1 | 서버를 멈춘다 | DB 파일을 쥐고 있는 프로세스가 없다 |
| 2 | `backend/.env`에 `SLOTFLOW_SESSION_SECRET`이 있는지 확인한다. 없으면 만든다 (6절) | 값을 화면·로그·채팅에 출력하지 않는다 |
| 3 | `backend/data/slot-flow.db`, `slot-flow.db-wal`, `slot-flow.db-shm`을 지운다 | 파일이 없다 |
| 4 | 새 구조의 서버 코드로 서버를 시작한다. 아래 순서로 테이블을 만든다: `accounts` → `sessions` → `login_failures` → `resources` → `operating_hours` → `reservations` → 인덱스 → 겹침 트리거 | 외래키가 가리키는 테이블을 먼저 만든다 |
| 5 | 같은 쓰기 단위 안에서 `PRAGMA user_version = 1`로 적는다 | `PRAGMA user_version`이 `1` |
| 6 | 관리자 계정을 서버 명령으로 만든다 (D-050). 비밀번호는 명령을 실행할 때 입력받는다 | `accounts`에 `role = 'admin'` 행이 하나 |
| 7 | 테스트를 실행한다 (5.4) | 모두 통과. 실패하면 멈춘다 (AGENTS.md) |

### 5.3 구조 버전
| `user_version` | 구조 | 서버 시작 때 동작 |
|---|---|---|
| 테이블이 없음 | — | 4번 순서대로 만들고 `1`로 적는다 |
| `0` + 테이블이 있음 | 이전 구조 (테이블 셋) | **시작하지 않는다.** "옛 DB 구조입니다. DATA-MIGRATION-PLAN 5.2를 따라 DB를 다시 만드세요"를 출력한다 |
| `1` | 이 문서의 구조 | 정상 시작 |
| `1`보다 큼 | 이 코드보다 새 구조 | 시작하지 않는다 |

- `CREATE TABLE IF NOT EXISTS`는 이미 있는 테이블에 컬럼을 더하지 않는다. 버전 검사가 없으면 옛 `resources`에 소유자 없이 쓰게 된다. (D-057)
- 앞으로 구조가 바뀌면(Q-25의 이름·예약 주소명 등) 버전을 올리고 이 문서에 그 단계를 더한다.

### 5.4 확인 항목 (테스트)
| # | 확인 | 기대 |
|---|---|---|
| 1 | 새 DB의 테이블 목록 | 여섯 개, 모두 `STRICT` |
| 2 | 두 번째 관리자 INSERT | 거부 |
| 3 | 대문자가 섞인 이메일 INSERT | 거부 (CHECK) |
| 4 | `$argon2id$`로 시작하지 않는 `password_hash` INSERT | 거부 |
| 5 | `role = 'customer'`인데 `operator_status`가 있는 행 | 거부 |
| 6 | `owner_account_id`가 없는 자원 INSERT | 거부 |
| 6-1 | 예약 주소명이 없는 운영자, 예약 주소명이 있는 고객 INSERT | 거부 |
| 6-2 | 같은 예약 주소명 두 번 INSERT, 대문자·`_`가 든 주소명 | 거부 |
| 6-3 | `failed_count = 6`인 `login_failures` | 거부 |
| 7 | 없는 계정을 가리키는 세션·자원·예약 INSERT | 거부 (외래키) |
| 8 | 비회원 예약 INSERT (`customer_account_id = NULL`) | 성공 |
| 9 | 겹침 트리거 (기존 테스트) | 그대로 통과 |
| 10 | `user_version = 0`인 옛 DB로 서버 시작 | 시작하지 않음 |

### 5.5 되돌리기
- 이전 커밋으로 코드를 되돌리고 DB 파일을 지운 뒤 서버를 시작하면 옛 구조(테이블 셋)로 다시 만들어진다.
- 새 구조에서 만든 계정·예약은 옮기지 않는다. 첫 버전은 배포 전이라 지켜야 할 운영 데이터가 없다. (F-04)

## 6. 비밀값 다루기

| 값 | 둘 곳 | 두지 않는 곳 |
|---|---|---|
| `SLOTFLOW_SESSION_SECRET` | `backend/.env`에만 (Git 제외, `.gitignore`의 `.env`) | Git, DB, API 응답, 오류 메시지, 로그, `/docs`, 화면 코드와 `frontend/.env`(`VITE_` 접두사 금지), 문서, 채팅 |
| 항목 이름 | `backend/.env.example` (값은 비워 둠) | — |
| 비밀번호 원문 | 어디에도 두지 않는다 | 로그·오류 메시지에도 남기지 않는다 |
| 세션 토큰 원문 | 브라우저의 HttpOnly 쿠키에만 | DB, 응답 본문, 로그 |

- 값 만들기: `python -c "import secrets; print(secrets.token_hex(32))"`의 결과를 직접 `backend/.env`에 붙여 넣는다. 결과를 공유하지 않는다.
- 비밀값이 없거나 32바이트(16진수 64자)보다 짧으면 서버가 시작하지 않는다. 시작 실패 메시지에 값은 넣지 않고 항목 이름만 넣는다. (D-049. 길이 기준은 이 문서에서 정함)
- 비밀값을 바꾸면 기존 세션은 모두 무효가 된다(HMAC 값이 맞지 않음). 새어 나갔다고 의심되면 값을 바꾸고 `sessions` 행을 모두 지운다.

## 7. DATA-MODEL 반영

이 계획대로 구현하고 테스트가 통과하면 `DATA-MODEL.md`의 1절(테이블 목록), 2절(테이블), 5절(인덱스), 7절(짝 맞추기)의 "4단계에서 설계" 항목을 이 문서의 내용으로 바꾼다.

## 8. 결정 필요

- Q-26: 비회원 예약을 계정에 연결
- Q-27: 정지된 운영자의 자원·예약 처리
- 계정 삭제와 외래키의 삭제 동작 (PRD에 없음)
- 예약 주소명 변경 (PRD에 없음)
