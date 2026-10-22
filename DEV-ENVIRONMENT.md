# DEV-ENVIRONMENT — 개발 환경 기록

확인일: 2026-10-19. 아래 버전은 각 도구의 `--version` 출력을 그대로 옮긴 것이다.

## 운영체제 · 셸

| 항목 | 값 |
|---|---|
| 운영체제 | Microsoft Windows 11 Pro 10.0.22631 (64비트) |
| 셸 | PowerShell 7.6.7 (Git Bash도 사용 가능) |

## 도구별 버전

| 도구 | 명령 | 출력 |
|---|---|---|
| git | `git --version` | `git version 2.56.0.windows.2` |
| node | `node --version` | `v24.21.0` |
| npm | `npm --version` | `11.19.0` |
| uv | `uv --version` | `uv 0.13.1 (62faed335 2026-10-13 x86_64-pc-windows-msvc)` |
| python | `python --version` | `Python` |
| python (uv 설치본) | `C:\Users\EZ\.local\bin\python3.12.exe --version` | `Python 3.12.15` |

참고: 셸의 `python`은 실제 Python이 아니라 Windows 스토어 안내용 껍데기(`C:\Users\EZ\AppData\Local\Microsoft\WindowsApps\python.exe`)라서 버전 번호가 나오지 않는다. 실제로 쓸 Python은 uv가 설치한 3.12.15(내장 SQLite 3.53.1)다.

## 새로 설치한 것

M0에서 아래 패키지를 설치했다 (2026-10-19). 위 도구 자체는 이전부터 설치돼 있었다.

- backend (uv, Python 3.12): fastapi, uvicorn[standard]
- frontend (npm): react, react-dom, vite, @vitejs/plugin-react, oxlint (Vite React 템플릿 기본)

M2에서 아래 패키지를 설치했다 (2026-10-22).

- backend (uv, Python 3.12): pwdlib[argon2] 0.3.1, alembic 1.20.1
