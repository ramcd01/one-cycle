# 관리자 페이지 (Admin)

## 프로젝트 개요

본 폴더는 LH 공고문 기반 AI 챗봇 프로젝트의 **관리자 페이지**입니다.

현재는 HTML, CSS, JavaScript 기반으로 구현되어 있으며,
추후 FastAPI API와 PostgreSQL(DB)을 연결할 수 있도록 구조를 설계했습니다.

---

# 폴더 구조

```
admin/
│
├── login.html                 # 관리자 로그인
├── announcement.html          # 공고 관리
├── document.html              # 문서 관리
├── error.html                 # 오류 관리
│
├── css/
│   ├── common.css             # 공통 스타일
│   ├── layout.css             # 관리자 레이아웃
│   ├── login.css
│   ├── announcement.css
│   ├── document.css
│   └── error.css
│
├── js/
│   ├── config.js              # 프로젝트 설정
│   ├── token.js               # Mock JWT 생성
│   ├── auth.js                # 로그인/로그아웃
│   ├── guard.js               # 페이지 접근 제어
│   ├── api.js                 # API 공통 함수
│   ├── common.js              # 공통 UI 기능
│   ├── login.js
│   ├── announcement.js
│   ├── document.js
│   └── error.js
│
├── components/
│   ├── sidebar.html
│   ├── header.html
│   ├── pagination.html
│   └── modal.html
│
└── assets/
```

---

# 현재 구현된 화면

- 관리자 로그인
- 공고 관리
- 문서 관리
- 오류 관리

로그인 성공 시

```
login.html
        ↓
announcement.html
```

으로 이동합니다.

---

# 테스트 계정

```
ID : admin
PW : admin1234
```

현재는 API가 없으므로 JavaScript 내부에서 확인합니다.

추후 FastAPI 로그인 API와 연결 예정입니다.

---

# 인증 구조 (API 연결 전)

현재는 실제 JWT가 아니라

**JWT와 동일한 구조를 흉내 낸 Mock JWT**

를 사용합니다.

로그인 성공

↓

Mock JWT 생성

↓

sessionStorage 저장

↓

관리자 페이지 접근 허용

↓

로그아웃 시 삭제

---

# 추가된 인증 모듈

## config.js

프로젝트 설정

```javascript
API_BASE_URL
USE_MOCK_AUTH
TOKEN_TTL
```

관리

---

## token.js

Mock JWT 생성

현재

```
Header.Payload.MockSignature
```

형태의 토큰을 생성합니다.

실제 보안 기능은 없습니다.

---

## auth.js

인증 관련 기능

- 로그인
- 로그아웃
- 현재 관리자 확인
- 토큰 저장
- 토큰 삭제

관리

---

## guard.js

관리자 페이지 접근 제어

```
로그인 X

↓

login.html 이동
```

---

## api.js

향후 FastAPI 연결을 위한 공통 fetch 함수

현재는 준비만 되어 있습니다.

---

# 현재 로그인 방식

```
login.html

↓

login.js

↓

auth.js

↓

Mock JWT 생성

↓

sessionStorage 저장

↓

announcement.html 이동
```

---

# 향후 API 연결

현재

```
login()

↓

Mock JWT 생성
```

↓

추후

```
login()

↓

POST /api/admin/auth/login

↓

FastAPI

↓

JWT 발급

↓

HttpOnly Cookie 저장
```

으로 변경됩니다.

HTML은 수정하지 않고

JavaScript 내부만 변경하면 됩니다.

---

# 향후 사용할 API

```
POST /api/admin/auth/login

POST /api/admin/auth/logout

GET /api/admin/auth/me
```

이 API를 기준으로 구현됩니다.

---

# 실행 방법

프로젝트 루트에서

```
python -m http.server 5500
```

실행

접속

```
http://localhost:5500/admin/login.html
```

---

# 현재 보안 수준

현재 인증은

**화면 개발을 위한 Mock 인증**

입니다.

실제 JWT 보안은 아닙니다.

---

# 실제 개발 시 변경 사항

FastAPI 구축 후

- JWT 발급
- HttpOnly Cookie 저장
- BCrypt(또는 Argon2) 비밀번호 해싱
- PostgreSQL 관리자 계정 조회
- 관리자 권한 검증
- Access Token 검증
- Logout API

를 적용합니다.

---

# 개발 순서

✔ 관리자 화면 제작

↓

✔ Mock JWT 인증

↓

✔ PostgreSQL 구축

↓

✔ SQLAlchemy 모델 작성

↓

✔ FastAPI API 구현

↓

✔ JWT 로그인

↓

✔ API 연결

↓

✔ 관리자 기능 연결

↓

✔ 배포