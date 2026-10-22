# DATA-MIGRATION-PLAN — 로그인 기능의 저장 구조 변경 (slot-flow)

근거 문서: `PRD.md`, `DECISIONS.md`, `DATA-MODEL.md`, `API-SPEC.md`, `API-SPEC-CHANGE.md`. US-xxx, Q-xxx, D-xxx, C-x는 이 문서들의 ID를 그대로 쓴다.
PRD Must의 R-018~R-023(계정·로그인)을 위해 저장 구조를 바꾸는 계획이다. 결정은 D-055~D-057, D-059, D-062~D-064다.
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
- 구조는 alembic 절차로 만들고 바꾼다. 계정 테이블은 0002, 소유자 컬럼은 0003(5단계), 회원 컬럼은 0004(7단계)에서 더한다. 기존 개발용 DB는 지우고 0001부터 새로 만들었다. (D-057, D-064, 5절)

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
- **비밀번호 값**: `pwdlib`(안에서 argon2-cffi를 씀)이 만든 문자열을 그대로 저장한다. 그 안에 알고리즘, 설정값, salt가 들어 있어 salt 컬럼을 따로 두지 않는다. 예: `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>` (D-063)
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
DB 구조는 alembic 절차로만 만들고 바꾼다. (D-064)

| 항목 | 내용 |
|---|---|
| 절차 위치 | `backend/migrations/versions/` |
| 설정 | `backend/alembic.ini`, `backend/migrations/env.py`. DB 경로는 `alembic.ini`에 적지 않고 `app.storage.db`를 따른다. 테스트의 `set_db_path`도 그대로 적용된다 |
| 절차 작성 | SQLAlchemy 모델을 두지 않고 `op.execute`로 SQL을 직접 쓴다. 자동 생성(autogenerate)과 batch 모드는 `STRICT`와 트리거를 잃을 수 있어 쓰지 않는다 |
| 절차 ID | `--rev-id 0001`처럼 순서가 보이는 ID를 붙인다 |
| 적용 시점 | 서버를 시작할 때 `init_db()`가 `upgrade head`를 부른다. DB 파일이 없으면 새로 만든다. 직접 적용할 때는 `backend`에서 `uv run alembic upgrade head` |
| 기록 | 적용한 절차는 DB의 `alembic_version` 테이블에 남는다 |
| 연결 설정 | 절차를 적용하는 연결도 `foreign_keys=ON`을 켠다. `journal_mode=WAL`은 적용 뒤 `connect()`가 켠다 (D-032) |
| 주의 | SQLite의 DDL은 alembic이 하나의 쓰기 단위로 묶지 않는다(non-transactional DDL). 절차가 중간에 실패하면 일부만 적용될 수 있으므로, 실패하면 원인을 고치고 DB를 확인한 뒤 다시 적용한다 |
| 주의 | `alembic.ini`는 ASCII로만 쓴다. alembic이 시스템 인코딩(Windows는 cp949)으로 읽어 한국어 주석이 있으면 실패한다 |

### 5.2 절차 목록
| 절차 | 단계 | 내용 | 방법 | 상태 |
|---|---|---|---|---|
| `0001` initial schema | — | M1의 구조: `resources`, `operating_hours`, `reservations`, 인덱스, 겹침 트리거 | `CREATE` SQL (이전 `db.py`의 `SCHEMA` 그대로) | 적용 |
| `0002` add accounts sessions login_failures | 1 저장 구조 | `accounts`, `sessions`, `login_failures`, 관리자 1명 인덱스, `sessions(account_id)` 인덱스 (2절) | `CREATE` SQL. 기존 테이블은 바꾸지 않음 | 적용 |
| `0003` add resources owner | 5 역할·소유 검사 | `resources.owner_account_id` 필수 컬럼, `resources(owner_account_id)` 인덱스 (3.1) | 기본값 없는 `NOT NULL` 외래키는 `ALTER`로 더할 수 없어, 새 테이블을 만들어 행을 옮기고 바꿔 끼운다. `STRICT`, 외래키, 트리거를 다시 만든다 | 그 단계에서 작성 |
| `0004` add reservations customer account | 7 회원 예약 | `reservations.customer_account_id` (NULL 허용), 인덱스 (3.2) | `ALTER TABLE ADD COLUMN` | 그 단계에서 작성 |

- 소유자 컬럼(0003)과 회원 컬럼(0004)을 그 기능의 단계에서 더하므로, 1~4단계 동안 기존 자원 등록과 예약이 그대로 동작한다.
- **0003의 기존 자원**: 소유자를 정할 수 없는 자원이 있으면 절차가 멈추고 "소유 운영자가 없는 자원이 있습니다"를 출력한다. 절차는 데이터를 지우지 않는다. 개발용 자원이면 직접 정리하고 다시 적용한다. (D-064)
- 기존 개발용 DB(구조 버전이 없던 파일)는 2026-10-22에 지웠다. 새 DB는 0001부터 적용해 만들었다. (D-057)

### 5.3 순서 (절차를 더할 때마다)
| # | 할 일 | 확인 |
|---|---|---|
| 1 | `backend/.env`에 `SLOTFLOW_SESSION_SECRET`이 있는지 확인한다. 없으면 만든다 (6절) | 값을 화면·로그·채팅에 출력하지 않는다 |
| 2 | 절차 파일을 만든다: `uv run alembic revision --rev-id 000N -m "<내용>"` | `migrations/versions/000N_<내용>.py` |
| 3 | `upgrade()`와 `downgrade()`를 SQL로 쓴다 | 되돌리기를 비워 두지 않는다 |
| 4 | 테스트를 실행한다 (5.4). 테스트는 임시 DB에 `upgrade head`를 적용한다 | 모두 통과. 실패하면 멈춘다 (AGENTS.md) |
| 5 | 실제 DB에 적용한다: 서버를 다시 시작하거나 `uv run alembic upgrade head` | `uv run alembic current`가 새 절차 ID |
| 6 | 관리자 계정이 없으면 서버 명령으로 만든다 (D-050, 2단계 이후) | `accounts`에 `role = 'admin'` 행이 하나 |

### 5.4 확인 항목 (테스트, `backend/tests/test_migrations.py`)
| # | 확인 | 기대 | 절차 |
|---|---|---|---|
| 1 | `upgrade head` 뒤의 테이블 목록 | 여섯 개, 모두 `STRICT`, `alembic_version`이 최신 | 0002 |
| 2 | `downgrade base` 뒤 다시 `upgrade head` | 테이블이 모두 지워졌다가 다시 생김 | 0001, 0002 |
| 3 | pwdlib이 만든 비밀번호 값 | `$argon2id$`로 시작하고 저장됨 | 0002 |
| 4 | 두 번째 관리자 INSERT | 거부 | 0002 |
| 5 | 대문자·`@` 없는 이메일, `$argon2id$`가 아닌 `password_hash` | 거부 | 0002 |
| 6 | 운영자 상태·예약 주소명이 역할과 맞지 않는 행 (고객인데 값이 있음, 운영자인데 없음) | 거부 | 0002 |
| 7 | 대문자·`_`·`-`로 시작·3자 미만인 예약 주소명, 같은 이메일·주소명 두 번 | 거부 | 0002 |
| 8 | 없는 계정을 가리키는 세션, 16진수가 아닌 `token_hash` | 거부 | 0002 |
| 9 | `login_failures`: `failed_count = 6`, 5인데 잠금 시각 없음, 5 미만인데 잠금 시각 있음 | 거부 | 0002 |
| 10 | 기존 테스트(자원·운영시간·예약·겹침 트리거) | 그대로 통과 | 0001 |
| 11 | `owner_account_id`가 없는 자원, 소유자 없는 자원이 있을 때 0003 적용 | 거부, 절차 멈춤 | 0003 (5단계) |
| 12 | 비회원 예약 INSERT (`customer_account_id = NULL`) | 성공 | 0004 (7단계) |

### 5.5 되돌리기
- `uv run alembic downgrade -1`은 마지막 절차 하나를, `uv run alembic downgrade base`는 전부를 되돌린다.
- 되돌리면 그 절차가 만든 테이블과 컬럼의 데이터는 사라진다. 배포 뒤에는 되돌리기 전에 DB 파일을 백업한다.

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
- 계정 삭제와 외래키의 삭제 동작 (PRD에 없음)
- 예약 주소명 변경 (PRD에 없음)
