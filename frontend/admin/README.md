# 관리자 페이지 (MVP API 연결 버전)

HTML/CSS/JavaScript 기반 관리자 화면입니다. 별도의 npm/React 환경이 필요하지 않습니다.

## 연결된 기능

- 관리자 로그인 / 로그아웃 / 현재 관리자 확인
- 공고 목록 / 상세 / 수집 요청
- 문서 목록 / 상세 / 재처리 요청
- 오류 목록 / 상세 / 재시도 요청
- FastAPI HttpOnly Cookie 인증

관리자 API는 `/api/admin/...` 경로를 사용합니다.

## 왜 serve_admin.py를 사용하나요?

관리자 화면은 정적 HTML이지만 FastAPI는 AWS 내부 `127.0.0.1:18000`에서 실행됩니다.

`serve_admin.py`는:

```text
브라우저
  ↓
Admin UI :5500
  ├─ HTML/CSS/JS 제공
  └─ /api/* → FastAPI :18000 프록시
```

형태로 동작합니다.

따라서 CORS 설정이나 브라우저에서 AWS 내부 주소를 직접 접근하는 문제 없이
HttpOnly Cookie 인증을 같은 Origin에서 사용할 수 있습니다.

## 실행

FastAPI가 먼저 실행 중이어야 합니다.

```bash
cd /home/ubuntu/ddokbot/one-cycle-integration/frontend/admin

/home/ubuntu/ddokbot/venvs/one-cycle/bin/python   serve_admin.py   --host 127.0.0.1   --port 5500   --api http://127.0.0.1:18000
```

정상 출력:

```text
Admin UI : http://127.0.0.1:5500
API proxy: http://127.0.0.1:18000
```

## 로컬 PC에서 접속

사용자 화면이 `localhost:55173`을 사용하고 있다면 관리자 화면은 예를 들어 `55174`를 사용합니다.

Windows 로컬 터미널:

```bash
ssh -L 55174:127.0.0.1:5500 ubuntu@<AWS_PUBLIC_IP>
```

브라우저:

```text
http://localhost:55174
```

## 인증

기존 Mock JWT는 제거하고 FastAPI 관리자 인증 API를 사용하도록 변경했습니다.

```text
POST /api/admin/auth/login
GET  /api/admin/auth/me
POST /api/admin/auth/logout
```

JWT는 HttpOnly Cookie에 저장되므로 JavaScript에서 토큰을 직접 저장하지 않습니다.

## 현재 MVP 주의사항

수집, 재처리, 오류 retry 기능은 FastAPI의 외부 파이프라인 연결 환경변수가 설정되어 있지 않으면
503을 반환할 수 있습니다. 이 경우 화면 조회/로그인 기능과는 별개입니다.

오류 상태 영구 변경 기능은 현재 화면에서 연결하지 않았습니다.
