# 한컴AI 프로젝트 DB 구조 및 연동 가이드

> 작성 기준: 2026-08-07  
> 목적: 백엔드/API/AI 파이프라인/프론트 작업자가 현재 데이터베이스 구조와 데이터 흐름을 동일하게 이해하도록 정리한 공유 문서

---

## 1. 현재 DB 구성 요약

현재 PostgreSQL + pgvector 기반으로 **서비스 테이블 13개**를 사용한다.

> PostgreSQL에서 `\dt` 실행 시 `alembic_version`까지 포함하여 총 14개 테이블이 표시된다.

### 서비스 테이블 13개

1. `system_state`
2. `collection_runs`
3. `announcements`
4. `documents`
5. `processing_runs`
6. `processing_artifacts`
7. `document_structures`
8. `key_information`
9. `chunk_sets`
10. `chunks`
11. `embeddings`
12. `admins`
13. `error_logs`

---

## 2. 전체 데이터 흐름

```text
system_state
└─ active_collection_run_id
       ↓
collection_runs
       ↓
announcements
├─ key_information
└─ documents
    ↓
processing_runs
├─ processing_artifacts
├─ document_structures
└─ chunk_sets
    ↓
   chunks
    ↓
 embeddings

admins
└─ 관리자 인증/권한

error_logs
├─ collection_run_id
├─ announcement_id
├─ document_id
└─ processing_run_id
```

실제 문서 처리 흐름은 다음과 같다.

```text
HWP/HWPX
→ 파싱
→ 정규화
→ 구조화
→ document_structures 저장
   ├→ 핵심 정보 추출 → key_information
   └→ 청킹 → chunk_sets / chunks
              ↓
          BGE-M3 Embedding
              ↓
           embeddings
              ↓
            Retrieval
              ↓
              RAG
```

---

## 3. 테이블별 역할

### 3.1 `system_state`

서비스가 사용자에게 노출할 **현재 활성 수집 데이터셋**을 지정한다.

주요 필드:

- `id`
- `active_collection_run_id`
- `updated_at`

현재 MVP에서는 `id = 1`인 singleton row를 사용한다.

사용자 공고 API는 전체 수집 이력을 그대로 조회하는 것이 아니라:

```text
system_state.active_collection_run_id
→ collection_runs
→ announcements
```

순서로 현재 서비스 대상 공고를 조회해야 한다.

관리자 페이지에서는 필요에 따라 전체 수집 이력을 조회할 수 있다.

---

### 3.2 `collection_runs`

공고 수집 작업의 **실행 단위**를 저장한다.

예:

```text
LH 공고 수집 1회 실행
→ collection_runs 1개 생성
→ 해당 실행에서 수집한 announcements 연결
```

주요 개념:

- 실행 식별자 `execution_id`
- 실행 상태
- 성공/실패/부분 성공
- 수집 건수
- 시작/종료 시각
- 오류 정보

---

### 3.3 `announcements`

LH 공고의 기본 정보를 저장한다.

주요 데이터:

- `collection_run_id`
- `source_announcement_id`
- `title`
- `detail_url`
- `region`
- `announcement_date`
- `publication_status`
- `created_at`

중요:

```text
(collection_run_id, source_announcement_id)
```

조합은 UNIQUE이다.

같은 LH 공고라도 서로 다른 수집 실행 이력을 구분할 수 있도록 설계되어 있다.

---

### 3.4 `documents`

공고에 연결된 HWP/HWPX 원본 문서 정보를 저장한다.

주요 데이터:

- `announcement_id`
- 파일명
- 문서 형식
- 저장 경로
- 파일 크기
- checksum
- 다운로드 상태
- 다운로드 오류

관계:

```text
announcement 1 : N documents
```

---

### 3.5 `processing_runs`

문서 파싱/정규화/구조화의 **처리 실행 이력**을 저장한다.

주요 데이터:

- `document_id`
- `execution_status`
- `verification_status`
- `current_stage`
- `pipeline_version`
- `output_root_path`
- `error_stage`
- `error_code`
- `error_message`
- warning/error count
- `started_at`
- `finished_at`
- `is_active`
- `activated_at`

실행 상태:

```text
pending
running
succeeded
failed
```

검증 상태:

```text
not_run
pending
pass
warning
fail
```

중요 제약:

```text
문서 1개당 active processing_run은 최대 1개
```

그리고 active 처리 결과는:

```text
execution_status = succeeded
verification_status = pass
activated_at IS NOT NULL
```

조건을 만족해야 한다.

---

### 3.6 `processing_artifacts`

파싱/정규화/구조화/검증 과정에서 생성되는 중간 산출물의 메타데이터를 저장한다.

예:

- parsed
- normalized
- structured
- verification
- log

현재 데모 데이터에서는 `0건`이어도 정상이다.

---

### 3.7 `document_structures`

구조화 파이프라인의 최종 JSON 결과를 저장한다.

주요 데이터:

- `processing_run_id`
- `schema_version`
- `structure_json`
- `element_count`
- `content_hash`

문단, 표, 셀, 순서, 위치 등 원문 구조를 보존한 결과가 저장된다.

---

### 3.8 `key_information`

사용자 공고 상세 화면의 **핵심 정보 카드**용 데이터를 저장한다.

주요 데이터:

- `announcement_id`
- `source_processing_run_id`
- `application_period`
- `eligibility`
- `supply_information`
- `income_asset_criteria`
- `required_documents`
- `winner_announcement`
- `contact_information`
- `extraction_status`
- `is_verified`

중요:

프론트/API에서 `application_start`, `application_end` 같은 값이 필요하더라도 이를 `announcements`에 중복 저장하지 않는다.

API가 `announcements + key_information`을 조합해서 응답한다.

---

### 3.9 `chunk_sets`

한 번의 Chunking 실행 결과 묶음을 저장한다.

주요 데이터:

- `processing_run_id`
- chunker version
- strategy
- config
- input version
- status
- `is_active`
- chunk count

한 processing run 안에서도 Chunking 전략이나 버전이 바뀔 수 있기 때문에 `chunks`와 별도로 관리한다.

---

### 3.10 `chunks`

RAG 검색에 사용하는 실제 검색 단위다.

주요 데이터:

- `chunk_set_id`
- `announcement_id`
- `document_id`
- external key
- chunk index
- `content`
- `search_text`
- `embedding_text`
- source metadata
- token count
- content hash

현재 데모 문서 기준:

```text
총 Chunk: 291
embedding_text 빈 값: 0
content 빈 값: 0
최소 token_count: 32
최대 token_count: 696
```

---

### 3.11 `embeddings`

Chunk별 임베딩 벡터를 저장한다.

현재 설계:

```text
model dimension = 1024
pgvector Vector(1024)
```

주요 데이터:

- `chunk_id`
- model name
- model version
- dimension
- normalized 여부
- embedding hash
- vector

현재 로컬 데모 DB에는 embedding이 아직 생성되지 않았다.

```text
embeddings = 0
```

이는 오류가 아니라 정상 상태다.

AWS 환경에서 BGE-M3를 실행하면서 채울 예정이다.

---

### 3.12 `admins`

관리자 로그인 및 권한 확인용 테이블이다.

주요 데이터:

- `id`
- `login_id`
- `password_hash`
- `name`
- `role`
- `is_active`
- `last_login_at`
- `created_at`
- `updated_at`

주의:

- 비밀번호 원문 저장 금지
- 반드시 hash만 저장
- MVP 기본 role은 `admin`

관리자 API에서 사용 예정:

```text
POST /api/admin/auth/login
GET  /api/admin/auth/me
POST /api/admin/auth/logout
```

---

### 3.13 `error_logs`

관리자 오류 관리 페이지에서 사용할 **오류 이력 테이블**이다.

연결 가능한 FK:

- `collection_run_id`
- `announcement_id`
- `document_id`
- `processing_run_id`

모든 FK는 nullable이다.

이유:

```text
수집 단계 실패
→ announcement/document가 아직 없을 수 있음

다운로드 단계 실패
→ processing_run이 아직 없을 수 있음

Embedding 실패
→ processing_run까지 존재
```

관련 객체가 삭제되더라도 오류 이력을 보존하기 위해 FK는:

```text
ON DELETE SET NULL
```

을 사용한다.

오류 유형:

```text
collection
download
parsing
normalizing
structuring
verification
chunking
embedding
database
rag
llm
```

오류 상태:

```text
unresolved
in_progress
resolved
```

주요 데이터:

- `error_type`
- `error_code`
- `stage`
- `message`
- `stack_trace`
- `status`
- `resolution`
- `created_at`
- `resolved_at`

관리자 API에서 사용 예정:

```text
GET   /api/admin/errors
GET   /api/admin/errors/{id}
PATCH /api/admin/errors/{id}/status
POST  /api/admin/errors/{id}/retry
```

---

## 4. 프론트/API 응답과 DB 컬럼은 동일하지 않음

매우 중요한 원칙이다.

```text
DB 물리 구조 ≠ API Response 구조
```

프론트가 아래 데이터를 요구한다고 해서:

```text
application_start
application_end
processing_status
analysis_status
collection_status
```

동일한 이름의 컬럼을 DB에 추가하지 않는다.

예를 들어 문서 관리 API 응답:

```json
{
  "document_id": 5,
  "processing_status": "COMPLETED",
  "analysis_status": "COMPLETED"
}
```

는 DB에서:

```text
documents
+
현재 active processing_runs.execution_status
+
processing_runs.verification_status
```

를 조회해서 API가 프론트 형식으로 변환한다.

마찬가지로 신청 기간은:

```text
announcements
+
key_information.application_period
```

를 조합한다.

---

## 5. 사용자 API에서 반드시 지켜야 할 조회 기준

### 공고 목록

사용자용 공고 목록은 반드시 현재 활성 수집본만 사용한다.

```text
system_state
→ active_collection_run_id
→ collection_runs
→ announcements
```

과거 collection run의 공고가 사용자 API에 섞이면 안 된다.

### 공고 상세

기본적으로 다음 데이터를 조합한다.

```text
announcements
+ documents
+ key_information
```

### AI 질의응답

질문 대상 `announcement_id` 범위를 벗어난 Chunk를 검색하면 안 된다.

```text
announcement_id
→ active processing_run
→ active chunk_set
→ chunks
→ embeddings
→ Retrieval
→ LLM
```

---

## 6. 관리자 API에서 필요한 데이터

### 공고 관리

예정 API:

```text
GET  /api/admin/announcements
GET  /api/admin/announcements/{id}
POST /api/admin/announcements/collect
POST /api/admin/announcements/{id}/recollect
```

관리자 API는 사용자 API와 달리 필요하면 과거 수집 이력까지 조회할 수 있다.

### 문서 관리

예정 API:

```text
GET  /api/admin/documents
GET  /api/admin/documents/{id}
GET  /api/admin/documents/{id}/download
POST /api/admin/documents/{id}/reprocess
```

재처리 요청은 API 내부에서 파싱/청킹/임베딩 로직을 새로 구현하는 것이 아니라 기존 AI 파이프라인을 호출해야 한다.

```text
API
→ pipeline 실행 요청
→ parsing
→ normalizing
→ structuring
→ verification
→ chunking
→ embedding
→ DB 상태 갱신
```

### 오류 관리

예정 API:

```text
GET   /api/admin/errors
GET   /api/admin/errors/{id}
PATCH /api/admin/errors/{id}/status
POST  /api/admin/errors/{id}/retry
```

---

## 7. 현재 데모 DB 상태

현재 로컬 DB의 실제 연결 상태는 검증 완료되었다.

```text
active_collection_run_id = 5
execution_id             = demo-announcement-001
collection_status        = success

announcement_id          = 5
document_id              = 5

processing_run_id        = 5
execution_status         = succeeded
verification_status      = pass
processing_active        = true

document_structure_id    = 1

key_information_id       = 1
key_info_status          = completed
key_info_verified        = true

chunk_set_id             = 2
chunk_status             = completed
chunk_active             = true

chunk_count              = 291
embedding_count          = 0
```

---

## 8. Demo seed 동작

`scripts/db/seed_demo_document.py`는 기존 demo collection run이 이미 있어도 단순 종료하지 않고 해당 run을 현재 활성 데이터셋으로 지정한다.

즉:

```text
system_state.active_collection_run_id = demo collection_run.id
```

를 자동으로 보장한다.

테스트 결과:

```text
active_collection_run_id = NULL
↓
seed_demo_document.py 실행
↓
active_collection_run_id = 5
```

복구 확인 완료.

---

## 9. Alembic 상태

현재 적용된 최신 revision:

```text
b328bf2c4b4e
```

Migration:

```text
add admin and error log tables
```

이전 revision:

```text
162529bf34d0
```

현재 확인 결과:

```text
alembic current
→ b328bf2c4b4e (head)

alembic check
→ No new upgrade operations detected.
```

### Alembic 실행 위치

중요:

```text
C:\Project\one-cycle
```

프로젝트 **루트에서 실행**해야 한다.

`alembic.ini`와 `migrations/`가 프로젝트 루트에 있다.

잘못된 예:

```text
C:\Project\one-cycle\backend> alembic ...
```

정상:

```text
C:\Project\one-cycle> alembic ...
```

---

## 10. 로컬 개발 환경

현재 기준:

```text
Python: 3.12.10
PostgreSQL: 16.x
pgvector: 0.8.2
SQLAlchemy: 2.0.51
Psycopg: 3.3.4
Alembic: 1.19.0
Python pgvector: 0.5.0
FastAPI port: 18000
```

Docker PostgreSQL container:

```text
one-cycle-postgres
```

DB:

```text
database: one_cycle
user: one_cycle
```

Docker Compose:

```text
infra/docker-compose.yml
```

---

## 11. 중요한 설계 원칙

현재 MVP에서는 아래 원칙을 유지한다.

### 중복 상태 컬럼을 추가하지 않음

추가하지 않을 컬럼 예:

```text
announcements.collection_status
documents.processing_status
documents.analysis_status
announcements.application_start
announcements.application_end
```

기존 정규화된 테이블을 조합해서 API에서 응답한다.

### 처리 이력 보존

문서를 다시 처리했다고 기존 processing run을 덮어쓰지 않는다.

```text
documents
→ processing_runs N개
→ 그중 is_active = true인 결과 1개
```

### Chunking/Embedding 버전 관리

Chunk를 문서에 직접 종속시키지 않고:

```text
processing_run
→ chunk_set
→ chunks
→ embeddings
```

로 관리한다.

### 사용자 서비스에는 활성 데이터만 노출

```text
system_state.active_collection_run_id
```

를 반드시 기준으로 한다.

### 관리자 화면에서는 이력 확인 가능

관리자 페이지는 현재 활성 데이터뿐 아니라 필요하면 실패/과거 처리 이력을 조회할 수 있다.

---

## 12. 현재 완료된 범위

### DB / Backend Infra

- PostgreSQL 구성
- pgvector 구성
- SQLAlchemy 연결
- Alembic 구성
- 13개 서비스 테이블 설계
- FK / Check Constraint / Unique Constraint
- 활성 collection run 관리
- 문서 처리 이력 관리
- 구조화 JSON 저장
- 핵심 정보 저장
- Chunk 저장
- Embedding 스키마
- 관리자 계정 스키마
- 오류 로그 스키마
- Demo seed
- Mapper 검증
- Alembic upgrade/check 검증
- 주요 INSERT/ROLLBACK 검증

### 문서 처리 데모

- 문서 구조화 완료
- key information 생성
- 291개 Chunk 생성
- Chunk embedding 입력 텍스트 검증

---

## 13. 아직 남은 핵심 작업

다음 핵심 단계는 AWS 환경이다.

```text
AWS 서버 준비
→ PostgreSQL + pgvector
→ 프로젝트 배포
→ DB migration
→ 데모/실제 데이터 준비
→ BGE-M3 Embedding
→ embeddings 저장
→ pgvector Retrieval
→ RAG
→ llama.cpp LLM
→ API 연결
→ Front-End E2E
```

현재 로컬에서는 embedding vector를 생성하지 않는다.

BGE-M3 실행은 AWS GPU 환경에서 진행하는 방향이다.

---

## 14. 코드 작업 시 주의사항

DB 구조를 임의로 변경하지 않는다.

특히 API 구현 중 필요한 응답 필드가 없다고 판단되더라도 바로 SQLAlchemy 모델/Alembic을 수정하지 말고 먼저 기존 테이블 조합으로 만들 수 있는지 확인한다.

DB 변경이 필요한 경우 사전에 공유해야 한다.

API 담당은 다음 영역을 직접 구현하지 않는다.

```text
Parser 내부
Normalizer 내부
Structure 생성 내부
Chunking 내부
Embedding 내부
RAG Retrieval 내부
```

API는 해당 서비스/파이프라인을 **호출하고 요청·응답을 연결하는 역할**을 담당한다.

---

## 15. 빠른 확인 명령

### DB 테이블

```bash
docker exec one-cycle-postgres psql -U one_cycle -d one_cycle -c "\\dt"
```

서비스 테이블 13개 + `alembic_version` = 총 14개가 표시되어야 한다.

### Alembic

```bash
alembic current
alembic check
```

현재 기대값:

```text
b328bf2c4b4e (head)
No new upgrade operations detected.
```

### Mapper

Windows CMD 기준:

```cmd
set PYTHONPATH=backend && python -c "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('mapper ok')"
```

기대값:

```text
mapper ok
```

---

## 16. 현재 DB 구조 한 줄 요약

> **공고 수집 이력 → 공고 → HWP/HWPX 문서 → 처리 실행 → 구조화 결과/핵심정보 → Chunk → Embedding을 추적 가능하게 관리하고, `system_state`로 현재 서비스 데이터를 선택하며, `admins`와 `error_logs`로 관리자 인증 및 운영 기능을 지원하는 구조이다.**
