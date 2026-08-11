# AWS MVP 통합 작업 현황

작성일: 2026-08-10
브랜치: share/aws-mvp-integration-20260810

## 1. 작업 목적

AWS 공용 환경에서 PostgreSQL/pgvector, FastAPI, RAG, 사용자 Frontend, 관리자 Frontend가 실제로 연결되는지 확인했다.
이번 작업의 목표는 기능 개선이 아니라 현재 MVP 통합 상태를 검증하고 팀원이 이어서 작업할 수 있도록 공유 가능한 상태로 정리하는 것이다.

## 2. 실행 환경

### PostgreSQL
- 서비스 DB 컨테이너: one-cycle-postgres
- DB: one_cycle
- Host: 127.0.0.1
- Port: 5432
- PostgreSQL + pgvector 사용
- one-cycle-db-test는 별도 연결 테스트용 DB이며 서비스 DB가 아님

### FastAPI
- 작업 경로: /home/ubuntu/ddokbot/one-cycle-integration
- Port: 18000
- 실행 전 .env를 process environment로 export해야 함
- 실행 명령:
  set -a
  source .env
  set +a
  /home/ubuntu/ddokbot/venvs/one-cycle-backend/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18000

주의: 위 명령은 향후 `one-cycle-backend` 환경으로 FastAPI를 교체 실행할 때의 기준 명령이다. 이번 최종 `/api/chat` HTTP 검증은 기존 127.0.0.1:18000 프로세스를 재시작하지 않고 수행했다.

### Frontend
- 사용자 Vite: 127.0.0.1:5173
- 사용자 SSH Tunnel: 127.0.0.1:55173
- 관리자 서버: 127.0.0.1:5500
- 관리자 SSH Tunnel: 127.0.0.1:55174
- 관리자 /api 요청은 FastAPI 127.0.0.1:18000으로 proxy

## 3. DB 및 RAG 통합 상태

현재 fixture 공고 1건을 기준으로 검증했다.

- announcement: 1건
- document: 1건
- chunk: 291건
- embedding: 291건
- embedding model: BAAI/bge-m3
- embedding dimension: 1024
- normalized embedding 사용
- 현재 테스트 문서: HWPX

기존 파일 기반 RAG 경로와 별도로 PostgreSQL + pgvector를 직접 조회하는 DB-first RAG 경로를 연결했다.

주요 파일:
- rag/db_pipeline.py
- rag/service.py

실제 동작 흐름:
사용자 질문
→ BGE-M3 query embedding
→ PostgreSQL + pgvector
→ 선택 공고 범위 Top-K Chunk 검색
→ Qwen2.5 7B
→ FastAPI /api/chat
→ 사용자 화면 답변 및 근거 표시

브라우저에서 질문 입력, AI 답변, evidence 반환, 근거 문단 모달까지 확인했다.

## 4. 사용자 Frontend

### 공고 목록
GET /api/announcements 연결 완료.

초기에는 API 응답 객체 전체를 배열처럼 처리하여
announcements.filter is not a function 오류가 발생했다.

실제 응답의 data.items를 목록 배열로 사용하도록 수정했고,
현재 DB 공고 1건이 사용자 목록에 정상 출력된다.

주의:
ListScreen.tsx에는 시연용 defaultAnnouncements fallback이 아직 남아 있다.

### 공고 상세
GET /api/announcements/{id} 호출 자체는 정상이다.

상세 API에는 다음 데이터가 정상적으로 존재한다.
- id
- title
- region
- announcementDate
- publicationStatus
- detailUrl
- documents
- keyInformation

keyInformation 주요 항목:
- applicationPeriod
- eligibility
- supplyInformation
- incomeAssetCriteria
- requiredDocuments
- winnerAnnouncement
- contactInformation

현재 문제는 API 연결이 아니라 Frontend 데이터 매핑이다.

DetailScreen.tsx에는 아직 다음 하드코딩이 남아 있다.
- 접수기간: 추후 안내 (상세 참조)
- 공급 위치/세대수: 해당 공고문 참조
- 신청 자격/소득 기준: 공고문 세부 요건 참조
- 제출 서류 일부 고정 배열
- 공고 상태 fallback

또한 API는 announcementDate/publicationStatus를 반환하지만
DetailScreen 일부 코드는 date/status를 사용한다.

따라서 현재 상태:
DB → FastAPI 상세 API 정상
FastAPI → Frontend fetch 정상
상세 API 응답 → DetailScreen 화면 매핑 미완료

### 상세 API 매핑 패치 시도
자동 패치를 시도했지만 현재 소스 문자열과 일치하지 않아 다음 오류로 중단됐다.

RuntimeError: 상세 API setCurrentNotice 구문을 찾지 못했습니다.

파일 저장 전에 중단되어 해당 패치는 반영되지 않았다.
이후 npm run build는 정상 성공했으며,
Vite에서도 기존 하드코딩 값이 그대로 남아 있음을 확인했다.

### 챗봇 초기 시연 메시지
상세 화면 진입 시 자동 표시되던 고정 사용자 질문/고정 AI 답변은 제거했다.
현재 messages는 빈 배열로 시작하며 실제 사용자 질문 시에만 /api/chat을 호출한다.

## 5. 관리자 Frontend

관리자 인증에 필요한 환경변수:
- ADMIN_ID
- ADMIN_PASSWORD
- ADMIN_JWT_SECRET

초기에는 해당 값이 .env와 FastAPI process environment에 없어 로그인이 실패했다.
환경변수를 추가하고 .env를 export한 뒤 FastAPI를 재시작하여 로그인 성공을 확인했다.

민감한 실제 비밀번호와 JWT Secret은 Git에 기록하지 않는다.

브라우저 확인 결과:
- 관리자 로그인: 정상
- 공고 관리: DB 공고 1건 출력, 상세 모달 정상
- 문서 관리: HWPX 문서 1건 출력, 처리 완료/분석 완료 상태 정상
- 오류 관리: 조회 정상, 현재 오류 0건

공고 수집/재처리처럼 DB를 변경하는 기능은 이번 검증에서 실행하지 않았다.

## 6. 환경변수 주의사항

.env는 Git에 커밋하지 않는다.

주요 환경변수:
- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- RAG_ANSWER_FUNCTION
- MVP_ANNOUNCEMENT_ID
- ADMIN_ID
- ADMIN_PASSWORD
- ADMIN_JWT_SECRET

현재 서비스 DB 포트는 5432이다.

## 7. 현재 검증 결과

완료:
- PostgreSQL 연결
- pgvector 연결
- FastAPI DB 연결
- 공고 목록 API
- 공고 상세 API
- /api/chat
- 사용자 공고 목록 DB 출력
- 사용자 챗봇 답변/근거 출력
- 관리자 로그인
- 관리자 공고/문서/오류 조회

미완료:
- DetailScreen.tsx 상세 API 필드 매핑
- keyInformation 기반 핵심 정보 카드 출력
- requiredDocuments 기반 제출 서류 출력
- 상세 서류 보기 버튼 실제 데이터 연결
- ListScreen 시연용 fallback 제거
- 사용자 페이지 전체 E2E 재검증

## 8. 다음 작업 우선순위

1. DetailScreen.tsx를 실제 상세 API 구조에 맞게 수정
2. keyInformation을 핵심 정보 카드에 연결
3. requiredDocuments를 제출 서류 영역에 연결
4. 시연용 fallback/하드코딩 제거
5. 사용자 페이지 전체 E2E 재검증

현재 단계에서는 새로운 RAG 기능이나 검색 품질 개선보다
DB/API 데이터를 사용자 Frontend에 정확하게 연결하는 작업이 우선이다.

---

## 실행 및 환경 재현 가이드

팀원이 현재 AWS MVP 통합 환경을 동일하게 실행하거나 재현하려면 다음 문서를 참고한다.

- `docs/AWS_MVP_RUNBOOK.md`
- `.env.example`

Runbook에는 `.env` 준비, PostgreSQL, llama.cpp, FastAPI, 사용자/관리자 Frontend, SSH Tunnel, API 및 브라우저 검증 절차가 정리되어 있다.

---

## 9. Document Pipeline → DB Persistence 통합 검증

### 작업 목적

기존 Document Pipeline의 최종 산출물을 PostgreSQL 서비스 DB에 저장하고,
DB-first RAG가 활성 처리 결과를 직접 조회하도록 연결했다.

최종 검증 흐름:

HWP/HWPX → Parser → Normalizer → Structure → Chunking
→ 대표 문서 선택 → BGE-M3 Embedding → PostgreSQL Persistence
→ ProcessingRun 활성화 → pgvector 검색 → llama.cpp → FastAPI /api/chat

### 대표 문서 선택 규칙

- HWPX가 존재하면 HWPX를 대표 문서로 사용한다.
- HWPX가 없고 HWP만 존재하면 HWP를 사용한다.

실제 Full Pipeline 처리 결과:

- announcement_001: HWPX, 291 chunks
- announcement_002: HWPX, 1246 chunks
- announcement_003: HWPX, 149 chunks
- announcement_004: HWP, 150 chunks
- 전체 Embedding 생성: 1,836개

### DB Persistence

추가 파일: `backend/app/services/pipeline_persistence.py`

주요 처리:

- canonical outputs 검증
- DB에 등록된 Announcement/Document와 대표 문서 일치 확인
- Structure verification=pass 확인
- Chunk ID 및 개수 검증
- BGE-M3 1024차원 Embedding 검증
- L2 normalization 검증
- ProcessingRun / DocumentStructure / ChunkSet 생성
- Chunk / Embedding 저장
- 전체 검증 성공 후 새 ProcessingRun 활성화

새 ProcessingRun과 ChunkSet은 먼저 inactive 상태로 저장한다.
모든 데이터 검증이 성공한 후에만 새 결과를 active로 전환한다.
따라서 새 처리 결과가 실패하면 기존 정상 active Run은 유지된다.

### Full Pipeline 실패 처리

`run_pipeline.py`의 Parser, Normalizer, Structure, Chunking, Embedding,
DB Persistence 단계가 성공/실패 값을 반환하도록 수정했다.

중간 단계가 실패하면 이후 단계를 실행하지 않는다.
DB Persistence 대상 공고가 0건인 경우에도 성공으로 처리하지 않는다.

### 실제 DB 검증 결과

- 서비스 DB 등록 대상: announcement_001
- ProcessingRun ID: 4
- ChunkSet ID: 4
- execution_status: succeeded
- verification_status: pass
- ProcessingRun active: true
- chunks: 291
- embeddings: 291
- 기존 active Run 2는 비활성화됨

announcement_002~004는 Document Pipeline과 Embedding까지 성공했지만
현재 서비스 DB에 Announcement/Document가 등록되어 있지 않아 Persistence 대상에서는 제외된다.

### DB-first Retrieval / RAG 검증

질문 `신청 자격은 어떻게 되나요?`에 대해 pgvector Top-1 결과가
`신청자격` 청크로 검색되었으며 similarity는 약 0.6146이었다.

DB-first RAG에서 BGE-M3 Query Embedding → pgvector Top-K → llama.cpp
답변 생성까지 정상 동작했다.

FastAPI 최종 검증:

- GET /docs: HTTP 200
- POST /api/chat: 정상 응답
- grounded: true
- evidence 반환 확인

따라서 문서 입력부터 FastAPI JSON 응답까지 백엔드 E2E가 확인되었다.

### Pipeline / DB-first RAG 직접 검증 환경

- Python venv: `/home/ubuntu/ddokbot/venvs/one-cycle-backend`
- GPU: NVIDIA L4
- Embedding: BAAI/bge-m3
- Embedding dimension: 1024
- CUDA 사용: true

- Full Pipeline, Embedding, DB Persistence, pgvector Retrieval, DBRAGPipeline 직접 검증은 위 `one-cycle-backend` 환경에서 수행했다.
- FastAPI `/api/chat` 최종 HTTP 검증은 기존 `127.0.0.1:18000`에서 실행 중이던 프로세스를 대상으로 수행했다.
- 기존 FastAPI 프로세스는 legacy `one-cycle` 환경에서 시작된 프로세스이므로, 교체 환경 검증 전에는 임의로 종료하거나 재시작하지 않는다.

주요 검증 패키지:

- FlagEmbedding==1.4.0
- numpy==2.5.1
- transformers==4.57.1
- tokenizers==0.22.2
- huggingface-hub==0.36.2
- accelerate==1.14.0
- safetensors==0.8.0
- tqdm==4.70.0
- sentencepiece==0.2.2
- torch==2.13.0
- cuda-toolkit==13.0.3.0
- triton==3.7.1

`pip check`와 `pip install --dry-run -r requirements.txt` 검증을 통과했다.

---

## 10. 사용자 Frontend E2E 및 공고 메타데이터 검증

사용자 Frontend를 실제 FastAPI 및 서비스 DB 데이터에 연결했다.

검증 흐름:

~~~text
React / Vite :5173
→ /api
→ Vite Proxy
→ FastAPI :18000
→ PostgreSQL
→ pgvector / RAG
→ llama.cpp
→ 답변 및 근거
→ 사용자 화면
~~~

### 공고 목록

`GET /api/announcements` 응답을 실제 목록 화면에 연결했다.

현재 `announcement_001` 기준:

- region: 충청북도
- announcementDate: 2026-07-16
- publicationStatus: fixture

`fixture`는 내부 테스트 적재 상태이므로 사용자 화면에서는
`상태 미확인`으로 표시한다.

파일명 기반 제목의 `_` 문자는 사용자 화면에서 공백으로 표시한다.

### 공고 상세

`GET /api/announcements/1` 응답의 `keyInformation`을 상세 화면에 연결했다.

현재 연결 항목:

- applicationPeriod
- supplyInformation
- eligibility
- incomeAssetCriteria
- requiredDocuments

### AI 질의응답

상세 화면의 질문 입력을 `/api/chat`에 연결했다.

`신청 자격은 어떻게 되나요?` 질문을 기준으로 다음을 확인했다.

- AI 답변 생성
- grounded 응답
- evidence 반환
- 근거 문단 버튼
- 근거 모달
- 검색 similarity 표시

### Frontend 검증

사용자 Frontend production build가 정상 완료되었다.

~~~bash
cd frontend/user
npm run build
~~~

Vite Proxy를 통한 API 연결도 확인했다.

~~~bash
curl -I http://127.0.0.1:5173
curl -sS http://127.0.0.1:5173/api/announcements/1
~~~

### Fixture 공고 메타데이터 재현

`backend/scripts/load_fixture_structure.py`에 다음 옵션을 추가했다.

- `--region`
- `--announcement-date`
- `--publication-status`

따라서 신규 fixture 초기 적재 시 지역과 공고일을 함께 등록할 수 있다.

현재 서비스 DB의 `announcement_001` 검증값:

- region: 충청북도
- announcement_date: 2026-07-16

현재 서비스 DB와 volume은 초기화하지 않는다.
