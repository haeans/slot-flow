# API-SPEC-CHANGE — 로그인 기능의 API 변경 (slot-flow)

근거 문서: `PRD.md`, `DECISIONS.md`, `API-SPEC.md`, `DATA-MODEL.md`, `DATA-MIGRATION-PLAN.md`. US-xxx, Q-xxx, D-xxx, C-x는 이 문서들의 ID를 그대로 쓴다.
PRD Must의 R-021(로그인·로그아웃)과 R-019·R-022(가입)를 위해 새로 생기는 요청 4개와, 로그인 뒤 막아야 하는 요청을 적는다. 결정은 D-055, D-056, D-058~D-062다.
공통 규칙(경로의 `/api`, JSON, 거부 응답 형식, 사유 코드)은 `API-SPEC.md` 1절을 따른다. 저장 구조는 `DATA-MIGRATION-PLAN.md`를 따른다.
아직 정해지지 않은 것은 **[결정 필요 Q-xx]** 또는 **[결정 필요: PRD에 없음]**으로 표시하고 이 문서에서 정하지 않는다.

---

## 1. 요약

### 1.1 새로 생기는 요청
| # | 메서드·경로 | 호출 주체 | 하는 일 | 근거 |
|---|---|---|---|---|
| 1 | `POST /api/auth/signup` | 누구나 | 운영자(승인 대기) 또는 회원 고객 계정을 만든다 | US-019, US-022 |
| 2 | `POST /api/auth/login` | 누구나 | 이메일·비밀번호를 확인하고 세션 쿠키를 보낸다 | US-021 |
| 3 | `POST /api/auth/logout` | 누구나 (세션이 없어도 됨) | 세션을 지우고 쿠키를 비운다 | US-021 |
| 4 | `GET /api/auth/me` | 로그인한 계정 | 지금 세션의 계정과 역할·운영자 상태를 알려 준다 | US-011, US-021 |

API-SPEC 2절과의 대응: 1 → #11·#12, 2 → #1, 3 → #2, 4는 새로 더한다. #13~#15(운영자 관리, 회원의 내 예약 목록)는 이 문서의 범위가 아니다.

### 1.2 이 4개를 고른 이유 (D-058)
| 고른 것 | 이유 |
|---|---|
| `me`를 둔다 | 세션 쿠키는 HttpOnly라 화면이 읽을 수 없다(D-049). 새로고침한 뒤 화면이 역할별 구역(`/admin`·`/operator`·고객)으로 보내고(D-047), 승인 대기 안내를 보여 주려면(D-053) 서버에 물어봐야 한다 |
| 가입을 하나로 묶는다 | 가입 항목(이메일·비밀번호·이름, D-059)이 운영자와 고객이 같고, 운영자만 예약 주소명 하나를 더 받는다. `role`로 그 필드의 필수 여부만 바꾸면 된다 |
| 관리자 가입은 없다 | 관리자는 서버 명령으로만 만든다(D-050). `role: "admin"`은 거부한다 |

### 1.3 새 사유 코드
| 상태 | code | 의미 | 근거 |
|---|---|---|---|
| 409 | `EMAIL_TAKEN` | 이미 가입된 이메일 | D-060 |
| 409 | `BOOKING_SLUG_TAKEN` | 이미 쓰는 예약 주소명 | D-060 |
| 404 | `OPERATOR_NOT_FOUND` | 고객이 조회한 예약 주소명의 승인된 운영자가 없음 | D-059, 3절 |
| 429 | `TOO_MANY_ATTEMPTS` | 같은 이메일로 5번 연속 로그인 실패, 10분 동안 잠김 | D-062 |
| 409 | `INVALID_OPERATOR_STATE` | 정지된 운영자를 다시 승인하려 함 | D-067 |

그 밖의 거부는 API-SPEC 1.6의 코드(`INVALID_INPUT`, `UNAUTHENTICATED`, `FORBIDDEN`, `OPERATOR_NOT_APPROVED`, `OPERATOR_SUSPENDED`)를 쓴다.

### 1.4 계정 객체
```json
{ "email": "owner@example.com", "name": "김공방", "role": "operator", "operator_status": "pending", "booking_slug": "kim-studio" }
```
- `booking_slug`: 운영자의 예약 주소명. 운영자가 아니면 `null` (D-059)
- `role`: `admin` / `operator` / `customer`
- `operator_status`: 운영자면 `pending`(승인 대기) / `approved`(승인) / `suspended`(정지), 아니면 `null`
- 내부 키(`accounts.id`), 비밀번호 값, 세션 토큰은 어떤 응답에도 담지 않는다. (6절)

### 1.5 세션 쿠키
| 항목 | 값 | 근거 |
|---|---|---|
| 이름 | `slotflow_session` | 이 문서에서 정함 |
| 값 | `secrets.token_urlsafe(32)`로 만든 토큰 원문 | D-049 |
| 속성 | `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age=604800`(7일), 배포 시 `Secure` | D-049 |
| DB | `HMAC-SHA256(SLOTFLOW_SESSION_SECRET, 토큰)`만 `sessions.token_hash`에 저장 | D-049, DATA-MIGRATION-PLAN 2.2 |

### 1.6 세션 확인 (모든 요청의 진입 단계, C-5)
1. `slotflow_session` 쿠키를 읽는다. 없으면 "세션 없음".
2. 토큰의 HMAC 값으로 `sessions`를 찾는다. 없으면 "세션 없음".
3. `expires_at <= 지금`이면 그 행을 지우고 "세션 없음".
4. 세션의 계정을 읽는다.
- "세션 없음"일 때 로그인이 필요한 요청은 `401 UNAUTHENTICATED`, 고객 요청은 비회원으로 처리한다. (D-051)

---

## 2. 새 요청

### 2.1 `POST /api/auth/signup` — 가입
1. **메서드와 경로**: `POST /api/auth/signup`
2. **호출 주체**: 누구나. 로그인한 상태에서 요청해도 지금 세션은 바꾸지 않는다.
3. **근거**: US-019, US-022 / D-042, D-043, D-055, D-056 / 가입 화면
4. **요청**
   | 필드 | 타입 | 필수 | 예 |
   |---|---|---|---|
   | `email` | string | 예 | `"owner@example.com"` |
   | `password` | string | 예 | (원문) |
   | `role` | `"operator"` / `"customer"` | 예 | `"operator"` |
   | `name` | string | 예 | `"김공방"` |
   | `booking_slug` | string | 운영자만 예 | `"kim-studio"` |
   - 이메일: 앞뒤 공백을 지우고 소문자로 바꾼다. 3~254자, `@`가 한 번 있고 앞뒤가 비어 있지 않으며, 공백이 없어야 한다. 메일 확인은 하지 않는다. (D-056, F-05)
   - 비밀번호: 8~128자. 앞뒤 공백을 지우지 않는다. (D-059)
   - 이름: 앞뒤 공백을 지운 1~50자. (D-059)
   - 예약 주소명: 영문 소문자·숫자·`-`, 3~30자, `-`로 시작하거나 끝나지 않음. 대문자는 소문자로 바꾸지 않고 거부한다. 고객이 보내면 `INVALID_INPUT`이다. (D-059)
5. **서버 판정 순서**
   1. 입력 형식 (`INVALID_INPUT`). `role`이 `admin`이거나 그 밖의 값이어도 `INVALID_INPUT`이다. (D-050)
   2. 비밀번호를 argon2id로 계산한다. 계산이 느리므로 쓰기 단위 밖에서 한다. (D-055)
   3. 쓰기 단위 시작 (`BEGIN IMMEDIATE`, D-035)
   4. 이메일 중복 (`EMAIL_TAKEN`, D-060)
   5. 예약 주소명 중복 (`BOOKING_SLUG_TAKEN`, 운영자만, D-060)
   6. 저장: `role = 'operator'`이면 `operator_status = 'pending'`, `customer`이면 `NULL` (D-043) → 쓰기 단위 끝
6. **성공 응답**: `201`, `{ "account": <계정 객체> }`. 세션은 만들지 않는다. 화면은 로그인 화면으로 보낸다.
7. **거부 응답**: `400 INVALID_INPUT`, `409 EMAIL_TAKEN`, `409 BOOKING_SLUG_TAKEN`
8. **실패 응답**: `500 STORAGE_ERROR`. 계정이 생기지 않는다.

### 2.2 `POST /api/auth/login` — 로그인
1. **메서드와 경로**: `POST /api/auth/login`
2. **호출 주체**: 누구나 (관리자·운영자·회원 고객의 로그인 화면은 하나, D-047)
3. **근거**: US-021 / D-049, D-053, D-054, D-055 / 로그인 화면
4. **요청**
   | 필드 | 타입 | 필수 | 예 |
   |---|---|---|---|
   | `email` | string | 예 | `"owner@example.com"` |
   | `password` | string | 예 | (원문) |
5. **서버 판정 순서**
   1. 입력 형식 (`INVALID_INPUT`). 이메일은 2.1처럼 정리한다.
   2. 그 이메일의 `login_failures`가 잠겨 있으면(`locked_until > 지금`) 비밀번호를 확인하지 않고 `TOO_MANY_ATTEMPTS`. 계정이 있든 없든 같다. (D-062)
   3. 이메일로 계정을 찾는다. 없으면 미리 만들어 둔 가짜 argon2 값으로 검증을 한 번 해서 응답 시간을 맞춘다. (D-054)
   4. `PasswordHash.verify_and_update`로 비밀번호를 확인한다. (D-063) 계정이 없거나 틀리면 쓰기 단위 안에서 `login_failures`를 1 올리고(5번째면 10분 잠금) `UNAUTHENTICATED`. 5번째 실패의 응답도 `UNAUTHENTICATED`이고, 그다음 요청부터 `TOO_MANY_ATTEMPTS`다. (D-054, D-062, DATA-MIGRATION-PLAN 2.3)
   5. 정지된 운영자면 `OPERATOR_SUSPENDED`. 비밀번호가 맞은 뒤에만 알린다. 그래야 비밀번호를 모르는 사람이 정지 여부를 알 수 없다. (D-053)
   6. 4번의 `verify_and_update`가 새 비밀번호 값을 돌려줬으면(설정이 바뀐 경우) 그 값을 저장한다. (D-063)
   7. 쓰기 단위 시작 → 그 이메일의 `login_failures` 행 삭제, 새 비밀번호 값 저장(6번), 세션 저장(`expires_at` = 지금 + 7일) → 쓰기 단위 끝
   8. `Set-Cookie`로 세션 쿠키를 보낸다. (1.5)
   - 같은 계정의 기존 세션은 지우지 않는다(다른 브라우저의 로그인 유지).
6. **성공 응답**: `200`, `{ "account": <계정 객체> }`. 승인 대기 운영자도 로그인에 성공한다(`operator_status: "pending"`). (D-053) 토큰은 본문에 담지 않는다.
7. **거부 응답**: `400 INVALID_INPUT`, `401 UNAUTHENTICATED`(계정 없음·비밀번호 틀림을 구분하지 않음), `403 OPERATOR_SUSPENDED`, `429 TOO_MANY_ATTEMPTS`
   - 동시에 여러 실패가 들어오면 `failed_count`는 쓰기 단위로 차례로 올라가므로 5를 넘지 않는다. 다만 잠기기 직전에 이미 검증 중이던 요청 몇 건은 더 확인될 수 있다.
8. **실패 응답**: `500 STORAGE_ERROR`. 쿠키를 보내지 않는다.

### 2.3 `POST /api/auth/logout` — 로그아웃
1. **메서드와 경로**: `POST /api/auth/logout`
2. **호출 주체**: 누구나. 세션이 없거나 만료돼도 거부하지 않는다.
3. **근거**: US-021 / D-047(d), D-049
4. **요청**: 본문 없음. 세션 쿠키.
5. **서버 판정 순서**: 쿠키가 있으면 그 HMAC 값의 `sessions` 행을 지운다 → 쿠키를 비운다(`Max-Age=0`)
6. **성공 응답**: `204`, 본문 없음. 세션이 없어도 같다. 화면은 응답과 관계없이 로그인 화면으로 간다. (D-047)
7. **거부 응답**: 없음
8. **실패 응답**: `500 STORAGE_ERROR`. 이때도 쿠키는 비운다.
- GET이 아닌 POST로 둔다. 다른 사이트의 링크·이미지로 로그아웃시키는 일을 막는다.

### 2.4 `GET /api/auth/me` — 내 계정 확인
1. **메서드와 경로**: `GET /api/auth/me`
2. **호출 주체**: 로그인한 계정 (모든 역할)
3. **근거**: US-011, US-021 / D-047, D-053, D-058 / 모든 화면의 진입
4. **요청**: 세션 쿠키
5. **서버 판정 순서**: 세션 확인 (1.6)
6. **성공 응답**: `200`, `{ "account": <계정 객체> }`. 화면은 `role`과 `operator_status`로 구역을 정하고 승인 대기 안내를 보여 준다.
7. **거부 응답**: `401 UNAUTHENTICATED`(세션 없음·만료). 정지된 운영자는 정지할 때 세션이 지워지므로 이 응답을 받는다. (D-053)
8. **실패 응답**: API-SPEC 1.6 공통 규칙
- 화면 표시용이다. 실제 차단은 각 요청의 진입 단계가 한다. (D-005)

### 2.5 운영자 관리 (관리자, API-SPEC 2절 #13·#14)
| 요청 | 하는 일 | 성공 응답 | 거부 응답 |
|---|---|---|---|
| `GET /api/admin/operators` | 운영자와 상태를 가입 순으로 읽는다 | `200`, `{ "operators": [<계정 객체>, …] }` | `401 UNAUTHENTICATED`, `403 FORBIDDEN` |
| `POST /api/admin/operators/{예약 주소명}/approve` | 승인 대기 → 승인 | `200`, `{ "operator": <계정 객체> }` | 위 + `404 OPERATOR_NOT_FOUND`, `409 INVALID_OPERATOR_STATE`(정지된 운영자) |
| `POST /api/admin/operators/{예약 주소명}/suspend` | 승인 대기·승인 → 정지. 같은 쓰기 단위에서 그 운영자의 세션을 모두 지운다 (D-053) | 같음 | 위 + `404 OPERATOR_NOT_FOUND` |

- 관리자 세션만 받는다. 운영자는 내부 키 대신 예약 주소명으로 가리킨다. (D-067)
- 이미 그 상태이면 바꾸지 않고 같은 응답을 준다.

---

## 3. 막을 요청

지금 구현에는 인증이 없어 아래 요청을 누구나 할 수 있다. 로그인 기능이 들어가면 진입 단계(C-5, C-9)에서 막는다. (D-005, D-043, D-044, D-052)

| 요청 | 지금 | 바뀐 뒤 호출 주체 | 막는 응답 (판정 순서대로) |
|---|---|---|---|
| `POST /api/resources` | 누구나 | 승인된 운영자 | 세션 없음 `401 UNAUTHENTICATED` → 운영자 아님 `403 FORBIDDEN` → 승인 대기 `403 OPERATOR_NOT_APPROVED` → 정지 `403 OPERATOR_SUSPENDED` |
| `PUT /api/resources/{resource_id}` | 누구나, 모든 자원 | 승인된 운영자, 자기 자원만 | 위와 같음 → 다른 운영자의 자원 `404 RESOURCE_NOT_FOUND` (C-9) |
| `GET /api/operator/reservations` | 누구나, 모든 자원 | 승인된 운영자, 자기 자원만 | 위와 같음 → 다른 운영자의 자원 `404 RESOURCE_NOT_FOUND` (C-9) |
| `GET /api/resources` | 누구나, 모든 자원 | 운영자: 자기 자원만. 고객: `?operator={예약 주소명}`의 운영자 자원 | `operator` 쿼리가 없으면 운영자 요청으로 보고 위와 같이 막는다(`401`·`403`). 쿼리가 있으면 세션을 보지 않고, 그 주소명의 승인된 운영자가 없으면 `404 OPERATOR_NOT_FOUND`(승인 대기 포함). 정지된 운영자의 주소도 `404 OPERATOR_NOT_FOUND` (D-059, D-065) |
| `POST /api/auth/signup` (`role: "admin"`) | — (새 요청) | 관리자 계정은 서버 명령으로만 | `400 INVALID_INPUT` (D-050) |

- 정지된 운영자는 세션이 지워져 보통 `401`을 받는다. `403 OPERATOR_SUSPENDED`는 정지와 요청이 거의 같은 때 들어온 경우를 위한 것이다. (D-052, D-053)
- 관리자도 운영자 요청에는 `403 FORBIDDEN`이다. 관리자가 다른 운영자의 자원을 고치는 기능은 없다. (D-043, D-044)
- `POST /api/resources`는 요청한 운영자를 `owner_account_id`로 저장한다. 본문으로 소유자를 받지 않는다. (D-044, DATA-MIGRATION-PLAN 3.1)

### 막지 않는 요청 (고객 요청, D-051)
| 요청 | 바뀌는 것 |
|---|---|
| `GET /api/resources/{resource_id}/slots` | 없음 |
| `POST /api/reservations` | 유효한 회원 세션이면 `customer_account_id`에 연결한다. 세션이 없거나 무효이면 비회원으로 처리하고 401을 내지 않는다. 운영자·관리자 세션이면 비회원으로 처리한다. (D-061) |
| `GET /api/reservations/{reservation_code}` | 없음 |
| `POST /api/reservations/{reservation_code}/cancel` | 없음. 회원 본인 확인으로 취소하는 경로는 이 문서의 범위가 아니다 |

---

## 4. 판정 위치

| 판정 | 위치 | 근거 |
|---|---|---|
| 세션 확인 (1.6) | 모든 요청의 진입 단계 (FastAPI 의존성 하나) | D-005, D-007 |
| 역할·운영자 상태 (C-5) | 운영자·관리자 요청의 진입 단계 | D-005, D-043, D-052 |
| 운영자 소유 (C-9) | 자원·예약을 다루는 운영자 요청. 자원 존재 확인과 같은 쓰기 단위 안 | D-044, D-035 |
| 비밀번호 계산·검증 | 계정 서비스 한 곳 (`pwdlib.PasswordHash.recommended()` 하나를 재사용) | D-007, D-063 |

---

## 5. CSRF

- API는 JSON 요청만 받는다(`Content-Type: application/json`이 아니면 `INVALID_INPUT`). 본문 없는 `logout`도 이 헤더를 요구한다.
- 쿠키가 `SameSite=Lax`이므로 다른 사이트의 POST에는 쿠키가 붙지 않는다. (D-049)
- 상태를 바꾸는 요청은 GET으로 두지 않는다.

## 6. 비밀값과 민감한 값

| 값 | 지키는 것 |
|---|---|
| `SLOTFLOW_SESSION_SECRET` | `backend/.env`에만 둔다. 어떤 응답, 오류 메시지, 로그, `/docs`(OpenAPI), Git, DB, 화면 코드에도 내보내지 않는다. `VITE_` 접두사를 붙이지 않는다(화면 번들에 들어감). 없거나 짧으면 서버가 시작하지 않고, 이때도 값은 출력하지 않는다. (D-049, DATA-MIGRATION-PLAN 6절) |
| 비밀번호 원문 | 요청 본문으로만 받는다. 저장·로그·응답·오류 메시지에 담지 않는다. 입력 검증 오류(422 → `INVALID_INPUT`, API-SPEC 1.5)의 메시지에도 입력값을 되돌려 담지 않는다 |
| 비밀번호 값(`password_hash`) | 응답에 담지 않는다 |
| 세션 토큰 원문 | `Set-Cookie`에만 담는다. 응답 본문·로그에 담지 않는다 |

## 7. 이 문서에서 정한 것

| 정한 것 | 이유 |
|---|---|
| 경로를 `/api/auth/…`로 묶는다 | 인증 요청을 한 라우터에 둔다 |
| 쿠키 이름 `slotflow_session` | D-049에 이름이 없다 |
| 가입 뒤 자동 로그인하지 않는다 | 승인 대기 운영자와 회원의 흐름을 같게 하고, 로그인 판정을 한 곳(2.2)에만 둔다 |
| 계정이 없을 때도 가짜 값으로 argon2 검증을 한다 | 응답 시간으로 계정이 있는지 알 수 없게 한다 (D-054) |
| 정지 여부는 비밀번호가 맞은 뒤에만 알린다 | 비밀번호를 모르는 사람이 계정 상태를 알 수 없게 한다 (D-053, D-054) |
| 로그아웃은 세션이 없어도 204 | 화면은 응답과 관계없이 인증 정보를 버린다 (D-047) |
| 비밀값은 32바이트 이상 | HMAC-SHA256 키 길이 |
| 고객의 자원 목록은 기존 `GET /api/resources`에 `operator` 쿼리를 더한다 | 새 요청을 늘리지 않고, 화면의 `/r/{예약 주소명}`에서 그대로 넘긴다 |
| 5번째 실패도 `401`, 잠금 응답은 그다음부터 | 잠기는 순간을 따로 알리지 않아 응답이 단순하다 |

## 8. 결정 필요

- 회원 예약의 `customer_name`, 운영자 관리·회원 예약 목록 API (#6·#7에서 더함)
- 회원 예약의 `customer_name`: 따로 보내는지, 계정 이름을 쓰는지 (API-SPEC 5.1)
- 예약 주소명 변경 (PRD에 없음)
