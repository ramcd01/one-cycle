# OneCycle Backend API 구현 가이드

이 문서는 OneCycle 프로젝트에서 **Frontend 관리자 화면 / 사용자 화면과 PostgreSQL, 수집·문서처리·AI 파이프라인을 연결하기 위해 구현한 FastAPI API 계층**을 설명합니다.

현재 기준 DB는 `feature/backend-infra`의 최신 구조를 전제로 하며, API 작업에서는 기존 SQLAlchemy 모델과 migration을 수정하지 않습니다.

---

## 1. API 계층의 역할

전체 흐름은 다음과 같습니다.

```text
React Frontend
    ↓ HTTP/JSON
FastAPI
├─ routes      : URL / Method / HTTP 상태코드
├─ schemas     : Request / Response JSON 계약
└─ services    : DB 조회 및 외부 파이프라인 호출
    ↓
PostgreSQL
    +
Crawler / Parser / Structure / Chunking / Embedding / RAG
```

API 담당 코드는 DB 테이블 구조 자체나 Parser, Chunking, Embedding 알고리즘을 구현하지 않습니다. 이미 존재하는 DB 데이터를 조회하거나, 실제 파이프라인 담당 코드의 실행 함수에 연결하는 역할을 합니다.

---

## 2. 수정/추가 파일

```text
backend/app/
├─ api/
│  ├─ router.py
│  ├─ dependencies.py
│  └─ routes/
│     ├─ health.py                 # 기존
│     ├─ announcements.py          # 사용자 공고 API
│     ├─ chat.py                   # 사용자 AI 질문 API
│     ├─ admin_auth.py             # 관리자 인증
│     └─ admin.py                  # 관리자 공고/문서/오류
│
├─ schemas/
│  ├─ common.py
│  ├─ announcement.py
│  ├─ chat.py
│  ├─ admin_auth.py
│  └─ admin.py
│
└─ services/
   ├─ announcement_service.py
   ├─ chat_service.py
   ├─ admin_auth_service.py
   ├─ admin_service.py
   └─ pipeline_gateway.py
```

`models/*`, `migrations/*`, `parser/*`, `normalizer/*`, `structure/*`, `chunking/*`, `embedding/*`는 수정하지 않습니다.

---

## 3. 공통 API Prefix

`backend/app/api/router.py`에서 다음 Prefix를 사용합니다.

```text
/api
```

따라서 최종 URL은 예를 들어 다음과 같습니다.

```text
/api/announcements
/api/chat
/api/admin/auth/login
/api/admin/documents
```

---

# 4. 관리자 인증

## API

```text
POST /api/admin/auth/login
GET  /api/admin/auth/me
POST /api/admin/auth/logout
```

## 구현 내용

- 관리자 ID/PW 검증
- HS256 JWT 생성/검증
- JWT를 HttpOnly Cookie에 저장
- 관리자 API 접근 시 Cookie 검증
- `role=admin` 확인
- 로그아웃 시 Cookie 삭제

### 중요: 현재 관리자 DB 테이블 없음

현재 DB 11개 핵심 테이블에는 `admin_users`가 없습니다.

따라서 DB를 임의로 변경하지 않고 **MVP에서는 `.env`의 관리자 계정값을 사용**합니다.

```env
ADMIN_ID=관리자아이디
ADMIN_PASSWORD=관리자비밀번호
ADMIN_JWT_SECRET=충분히긴랜덤문자열
ADMIN_JWT_EXPIRE_SECONDS=3600

# 로컬 HTTP 테스트
ADMIN_COOKIE_SECURE=false
ADMIN_COOKIE_SAMESITE=lax
ADMIN_COOKIE_NAME=admin_access_token
```

운영 단계에서 관리자 테이블이 추가되면 `admin_auth_service.authenticate_admin()` 내부만 DB 조회 및 해시 비밀번호 검증으로 교체하면 됩니다.

> 실제 비밀번호와 JWT Secret은 Git에 올리지 않습니다.

---

# 5. 사용자 API

## 5.1 공고 목록

```text
GET /api/announcements
```

사용자 서비스는 원칙적으로:

```text
system_state.active_collection_run_id
→ announcements.collection_run_id
```

가 일치하는 **현재 활성 수집 데이터만 조회**합니다.

지원 Query:

```text
page
size
search
region
status
```

응답:

```json
{
  "items": [
    {
      "id": 5,
      "title": "공고명",
      "region": "서울",
      "announcementDate": "2026-07-16",
      "publicationStatus": "게시중"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

---

## 5.2 공고 상세

```text
GET /api/announcements/{announcement_id}
```

조회 데이터:

```text
announcements
├─ documents
└─ key_information
```

`key_information`의 JSONB 필드는 LLM을 다시 호출하지 않고 DB 값을 그대로 반환합니다.

```text
application_period
eligibility
supply_information
income_asset_criteria
required_documents
winner_announcement
contact_information
```

---

## 5.3 AI 질문

```text
POST /api/chat
```

Request:

```json
{
  "announcementId": 5,
  "question": "신청 기간은 언제인가요?"
}
```

API 코드 내부에서 BGE-M3, pgvector, llama.cpp를 직접 구현하지 않습니다.

RAG 담당 함수:

```python
answer_question(
    announcement_id: int,
    question: str,
)
```

의 위치를 `.env`에 연결합니다.

```env
RAG_ANSWER_FUNCTION=모듈경로:answer_question
```

예:

```env
RAG_ANSWER_FUNCTION=rag.service:answer_question
```

RAG 함수가 아직 준비되지 않았다면 `/api/chat`은 가짜 답변을 만들지 않고 `503`을 반환합니다.

---

# 6. 관리자 공고 관리

## API

```text
GET  /api/admin/announcements
GET  /api/admin/announcements/{id}
POST /api/admin/announcements/collect
POST /api/admin/announcements/{id}/recollect
```

모든 관리자 API는 로그인 Cookie가 없거나 JWT가 유효하지 않으면 `401`을 반환합니다.

### 목록 Query

```text
page
size
search
region
announcement_status
collection_status
created_from
created_to
```

### 응답 필드

```text
id
title
region
announcement_date
application_start
application_end
announcement_status
collection_status
created_at
```

`application_start`, `application_end`는 `key_information.application_period` JSON에서 일반적인 start/end 키를 찾아 조립합니다. 실제 KeyInformation JSON 최종 구조가 확정되면 키 이름을 고정하는 것이 좋습니다.

---

# 7. 공고 수집 / 재수집 연결

API 계층에서 Crawler를 새로 구현하지 않습니다.

실제 수집 함수를 다음 환경변수로 연결합니다.

```env
COLLECTION_RUNNER=모듈경로:함수명
ANNOUNCEMENT_RECOLLECTOR=모듈경로:함수명
```

호출 계약:

```python
collect()

recollect(
    announcement_id=5
)
```

파이프라인 함수가 아직 준비되지 않은 경우 API는 `503`을 반환하며 가짜 성공을 반환하지 않습니다.

---

# 8. 관리자 문서 관리

## API

```text
GET  /api/admin/documents
GET  /api/admin/documents/{id}
GET  /api/admin/documents/{id}/download
POST /api/admin/documents/{id}/reprocess
```

### 목록 검색/필터

```text
search
  → 공고명 또는 문서명

document_type
processing_status
analysis_status

page
size
```

### 목록 응답

```text
id
announcement_id
announcement_title
file_name
document_type
file_size
download_status
processing_status
analysis_status
created_at
```

`processing_status`는 최신 `processing_runs.execution_status`, `analysis_status`는 최신 `verification_status`를 사용합니다.

---

## 8.1 문서 상세

문서 상세 API에서는 다음 상태를 한 번에 조립합니다.

```text
documents
    ↓
최신 processing_runs
    ↓
document_structures
    ↓
chunk_sets
    ↓
chunks
    ↓
embeddings
```

응답 예:

```json
{
  "id": 5,
  "announcement_id": 1,
  "announcement_title": "공고명",
  "file_name": "공고.hwpx",
  "document_type": "hwpx",
  "file_size": 123456,
  "download_status": "completed",
  "processing_status": "succeeded",
  "analysis_status": "pass",
  "processing": {
    "run_id": 12,
    "execution_status": "succeeded",
    "verification_status": "pass",
    "current_stage": "embedding"
  },
  "structure": {
    "schema_version": "1.2",
    "element_count": 154
  },
  "chunking": {
    "status": "completed",
    "chunk_count": 291
  },
  "embedding": {
    "completed_count": 291,
    "total_count": 291,
    "failed_count": 0
  }
}
```

---

## 8.2 문서 다운로드

```text
GET /api/admin/documents/{id}/download
```

`documents.storage_path`가 실제 파일을 가리키는 경우 `FileResponse`로 반환합니다.

- 문서 없음 → `404`
- DB에는 문서가 있지만 파일 경로가 없거나 실제 파일이 없음 → `409`

배포 환경에서는 `storage_path`가 API 서버 컨테이너에서도 접근 가능한 경로인지 확인해야 합니다.

---

## 8.3 문서 재처리

```text
POST /api/admin/documents/{id}/reprocess
```

API에서 Parser 등을 직접 구현하지 않고 실제 전체 파이프라인 실행 함수에 연결합니다.

```env
DOCUMENT_REPROCESSOR=모듈경로:함수명
```

호출 계약:

```python
reprocess_document(
    document_id=5
)
```

실제 함수에서는 다음 처리를 담당합니다.

```text
파싱
→ 정규화/구조화
→ 청킹
→ 임베딩
→ DB 저장
```

---

# 9. 관리자 오류 관리

## API

```text
GET   /api/admin/errors
GET   /api/admin/errors/{id}
PATCH /api/admin/errors/{id}/status
POST  /api/admin/errors/{id}/retry
```

## 현재 오류 조회 원천

현재 DB에는 별도의 `errors` 테이블이 없습니다.

따라서 조회 API는 다음 실패 데이터를 합쳐 하나의 오류 목록으로 제공합니다.

```text
documents.download_status = failed
processing_runs.execution_status = failed
embeddings.status = failed
```

오류 ID는 원본 데이터의 종류를 구분하기 위해 다음처럼 반환합니다.

```text
document:5
processing:12
embedding:200
```

---

## 9.1 오류 검색/필터

```text
search
  → 공고명 또는 오류 내용

error_type
status
occurred_from
occurred_to

page
size
```

현재 DB에서 오류 처리상태를 저장할 곳이 없으므로 조회된 오류의 기본 상태는 `open`입니다.

---

## 9.2 오류 상태 변경의 현재 제한

요구 API:

```text
PATCH /api/admin/errors/{id}/status
```

에는:

```text
status
resolution
resolved_at
```

을 영구 저장할 DB 구조가 필요합니다.

하지만 현재 DB에는:

```text
errors 테이블 없음
resolution 컬럼 없음
resolved_at 컬럼 없음
```

상태입니다.

API 담당자가 임의로 `processing_runs` 등에 다른 의미의 값을 저장하면 데이터 모델이 깨질 수 있으므로, 이 endpoint는 현재 **501 Not Implemented**를 반환하도록 만들었습니다.

DB 담당자에게 다음 중 하나가 필요하다고 공유해야 합니다.

```text
1. errors 테이블 추가

또는

2. 별도 error management/status 테이블 추가
```

DB 구조가 추가되면 `admin_service.update_error_status()`만 실제 UPDATE 로직으로 교체할 수 있습니다.

---

## 9.3 오류 재처리

```text
POST /api/admin/errors/{id}/retry
```

오류의 `stage`를 확인한 후 외부 실행 함수에 전달합니다.

```env
ERROR_RETRY_RUNNER=모듈경로:함수명
```

호출 형태:

```python
retry_from_stage(
    error_id="processing:12",
    document_id=5,
    start_stage="embedding"
)
```

따라서 Embedding 단계 실패라면 실제 파이프라인 구현에서 Embedding부터 재시작할 수 있습니다.

---

# 10. 관리자 처리 이력

기존 DB 상태 확인을 위해 다음 조회 API도 유지합니다.

```text
GET /api/admin/processing-runs
```

응답:

```text
관련 공고
관련 문서
execution_status
verification_status
current_stage
error_stage
error_code
error_message
started_at
finished_at
```

---

# 11. 페이지네이션 규칙

목록 API는 동일한 응답 형식을 사용합니다.

```json
{
  "items": [],
  "page": 1,
  "size": 10,
  "total": 50,
  "total_pages": 5
}
```

DB에서는 전체 데이터를 모두 읽은 뒤 `len()`을 계산하지 않고:

```text
COUNT(*)
LIMIT
OFFSET
```

방식으로 조회합니다.

---

# 12. HTTP 상태 코드

```text
200  정상 조회/로그인/로그아웃
201  수집/재처리/재시도 요청 전달
400  잘못된 요청
401  관리자 로그인 필요 또는 토큰 오류
403  관리자 권한 없음
404  데이터 없음
409  데이터는 있으나 현재 작업 불가
422  FastAPI/Pydantic 입력 검증 오류
501  현재 DB 구조로 구현 불가능한 기능
503  DB 또는 외부 파이프라인 미연결
500  예상하지 못한 서버 오류
```

---

# 13. Swagger 테스트

프로젝트 루트:

```bash
cd C:\Project\one-cycle
```

실행:

```bash
uvicorn backend.app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

DB가 연결되지 않아도 서버 기동과 Swagger API 등록은 확인할 수 있습니다.

DB 미연결 시 DB 조회 API의 `503`은 정상적인 연결 전 상태입니다.

---

# 14. 관리자 인증 테스트 순서

`.env`에 최소:

```env
ADMIN_ID=admin
ADMIN_PASSWORD=로컬테스트비밀번호
ADMIN_JWT_SECRET=로컬테스트용으로도충분히긴랜덤문자열
ADMIN_COOKIE_SECURE=false
```

설정 후 서버를 재시작합니다.

Swagger에서:

```text
POST /api/admin/auth/login
```

Request:

```json
{
  "admin_id": "admin",
  "password": "로컬테스트비밀번호"
}
```

로그인 성공 후 브라우저 Cookie에 `admin_access_token`이 저장됩니다.

이후:

```text
GET /api/admin/auth/me
```

를 확인하고 관리자 조회 API를 실행합니다.

---

# 15. 현재 구현 가능 여부 요약

| 기능 | 상태 |
|---|---|
| 관리자 로그인 API | 구현 |
| JWT 생성/검증 | 구현 |
| HttpOnly Cookie | 구현 |
| 관리자 권한 검사 | 구현 |
| 공고 목록/상세 | 구현 |
| 공고 검색/필터/페이지네이션 | 구현 |
| 공고 수집/재수집 API | 연결 지점 구현 |
| 문서 목록/상세 | 구현 |
| 문서 검색/필터/페이지네이션 | 구현 |
| 문서 다운로드 | 구현 |
| 문서 재처리 API | 연결 지점 구현 |
| 처리 이력 | 구현 |
| 오류 목록/상세 | 구현 |
| 오류 검색/필터/페이지네이션 | 구현 |
| 오류 상태 영구 변경 | DB 스키마 부족으로 501 |
| 오류 단계별 retry API | 연결 지점 구현 |
| RAG `/api/chat` | `answer_question()` 연결 지점 구현 |
| Parser/Chunking/Embedding 내부 | API 범위 아님 / 수정 안 함 |
| DB 모델/Migration | 수정 안 함 |

---

# 16. 프론트 담당자에게 전달할 핵심

관리자 API는 로그인 후 HttpOnly Cookie를 사용하므로 프론트에서 API 서버가 다른 Origin이라면 요청 시 Cookie를 포함해야 합니다.

Fetch 예:

```typescript
fetch("http://127.0.0.1:8000/api/admin/documents", {
  credentials: "include"
});
```

Axios:

```typescript
axios.get(
  "http://127.0.0.1:8000/api/admin/documents",
  { withCredentials: true }
);
```

Frontend와 Backend Origin이 다르면 FastAPI CORS 설정에서도 credentials 허용이 필요합니다. 현재 프로젝트 CORS 설정은 별도로 확인해야 합니다.

---

# 17. Git에 올리기 전 확인

API 코드만 별도 feature branch에 올리는 것을 권장합니다.

최소 실행 확인:

```text
□ uvicorn 서버가 에러 없이 시작됨
□ /docs 접속됨
□ Admin Auth API 3개 노출됨
□ Admin Announcement API 4개 노출됨
□ Admin Document API 4개 노출됨
□ Admin Error API 4개 노출됨
□ /api/admin/processing-runs 노출됨
□ 사용자 announcements/chat API 노출됨
```

DB 연결 전에는 DB 조회 결과까지 검증할 수 없지만, **서버 기동과 Swagger Schema 확인은 반드시 완료한 뒤 프론트에 전달**하는 것이 좋습니다.
