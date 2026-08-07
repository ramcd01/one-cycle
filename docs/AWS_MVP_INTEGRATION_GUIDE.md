# 한컴AI AWS MVP 통합 환경 가이드

## 1. 문서 목적

이 문서는 현재 AWS 서버에 구축된 한컴AI MVP 통합 환경의 위치와 상태를 정리하고, 팀원이 동일한 코드·DB·AI 처리 결과를 직접 확인한 뒤 후속 MVP 개발을 이어갈 수 있도록 하기 위한 인수인계 문서이다.

현재 `announcement_001` 1건을 대표 공고로 사용하여 다음 백엔드 AI 흐름까지 AWS에서 실제 연결 및 검증을 완료했다.

```text
HWP/HWPX 문서 처리
    ↓
Structure JSON 생성
    ↓
PostgreSQL document_structures 저장
    ↓
DB Structure 기반 Chunk 생성
    ↓
chunks 저장
    ↓
BGE-M3 Embedding 생성
    ↓
embeddings / pgvector 저장
    ↓
질문 Embedding
    ↓
선택 공고 범위 pgvector 검색
    ↓
Top-K 근거
    ↓
Prompt 생성
    ↓
llama.cpp / Qwen2.5-7B
    ↓
근거 기반 답변
```

현재 팀원 모두 AWS 서버에 SSH 접속할 수 있으므로 같은 AWS 서비스 DB와 적재 결과를 직접 확인할 수 있다.

다음 MVP 작업은 현재 검증된 DB-first RAG 흐름을 FastAPI에 연결하고, 이후 React와 연결하여 브라우저 기준 전체 E2E를 완성하는 것이다.

---

# 2. Git 기준

## 기준 브랜치

현재 통합 기준 브랜치는 다음과 같다.

```text
feature/rag
```

AWS에서 검증한 DB-first RAG 관련 코드도 해당 브랜치에 반영되어 있다.

현재 주요 커밋:

```text
fc3f663 feat: integrate db-first rag pipeline
b6e8eed feat: add structure fixture database loader
```

코드를 확인할 때는 `feature/rag`를 기준으로 한다.

```bash
git fetch origin feature/rag
git log --oneline origin/feature/rag -5
```

후속 개발을 진행하는 팀원도 자신의 작업 환경에서 최신 `feature/rag`를 기준으로 코드를 확인한다.

---

# 3. AWS 프로젝트 위치

현재 통합 검증에 사용한 AWS 프로젝트 경로:

```text
/home/ubuntu/ddokbot/one-cycle-integration
```

AWS 접속 후:

```bash
cd /home/ubuntu/ddokbot/one-cycle-integration
```

현재 AWS에서 검증한 코드와 실행 경로를 확인할 때는 이 디렉터리를 기준으로 한다.

## 기존 프로젝트 경로 주의

AWS에는 기존 작업 경로도 존재한다.

```text
/home/ubuntu/ddokbot/one-cycle
```

이 경로에는 기존 팀원 작업 이력이 남아 있으므로 현재 통합 검증 결과를 확인할 때는 우선 다음 경로를 사용한다.

```text
/home/ubuntu/ddokbot/one-cycle-integration
```

기존 작업을 보호하기 위해 다른 팀원의 작업 내용을 확인하지 않은 상태에서 임의로 아래 명령을 실행하지 않는다.

```text
git reset --hard
git rebase
git clean -fd
```

---

# 4. 현재 주요 코드 위치

## 4.1 Structure DB 적재

프로젝트 상대 경로:

```text
backend/scripts/load_fixture_structure.py
```

AWS 전체 경로:

```text
/home/ubuntu/ddokbot/one-cycle-integration/backend/scripts/load_fixture_structure.py
```

역할:

```text
Structure 결과
    ↓
CollectionRun
Announcement
Document
ProcessingRun
DocumentStructure
    ↓
PostgreSQL 저장
```

이 단계에서 이후 Chunking의 입력이 되는 Structure JSON이 다음 컬럼에 저장된다.

```text
document_structures.structure_json
```

---

## 4.2 DB Structure → Chunk 생성 및 DB 저장

프로젝트 상대 경로:

```text
backend/scripts/load_fixture_chunks_from_db.py
```

AWS 전체 경로:

```text
/home/ubuntu/ddokbot/one-cycle-integration/backend/scripts/load_fixture_chunks_from_db.py
```

이 스크립트는 원본 HWP/HWPX 파일을 다시 읽어서 Chunk를 생성하는 것이 아니라 다음 DB 데이터를 입력으로 사용한다.

```text
document_structures.structure_json
```

처리 흐름:

```text
PostgreSQL
document_structures.structure_json
    ↓
StructureAwareChunker
    ↓
Chunk 생성
    ↓
chunk_sets
chunks
```

현재 `announcement_001` 결과:

```text
ChunkSet  1개
Chunks    291개
```

주의:

현재 DB에는 이미 `announcement_001`의 ChunkSet과 Chunk가 저장되어 있다.

해당 스크립트는 같은 ProcessingRun에 기존 ChunkSet이 존재하면 중복 생성을 막도록 되어 있으므로, 단순 확인을 위해 `--write`를 다시 실행할 필요는 없다.

---

## 4.3 DB Chunk → Embedding 생성 및 DB 저장

프로젝트 상대 경로:

```text
backend/scripts/load_fixture_embeddings_from_db.py
```

AWS 전체 경로:

```text
/home/ubuntu/ddokbot/one-cycle-integration/backend/scripts/load_fixture_embeddings_from_db.py
```

입력:

```text
chunks.embedding_text
```

사용 Embedding 모델:

```text
BAAI/bge-m3
```

Vector dimension:

```text
1024
```

처리 흐름:

```text
PostgreSQL chunks
    ↓
embedding_text
    ↓
BGE-M3
    ↓
1024차원 Vector
    ↓
PostgreSQL embeddings
```

현재 `announcement_001` 결과:

```text
Chunks       291
Embeddings   291
```

현재 DB에는 이미 Embedding이 저장되어 있으므로 단순 확인을 위해 다시 DB write를 실행하지 않는다.

---

## 4.4 RAG Generation

프로젝트 상대 경로:

```text
rag/generation/
```

AWS 전체 경로:

```text
/home/ubuntu/ddokbot/one-cycle-integration/rag/generation
```

주요 파일:

```text
rag/generation/config.py
rag/generation/models.py
rag/generation/context_builder.py
rag/generation/prompt_builder.py
rag/generation/llm_client.py
rag/generation/generator.py
```

역할:

```text
검색된 Top-K Chunk
    ↓
SourceContext 구성
    ↓
Prompt Builder
    ↓
llama.cpp /v1/chat/completions
    ↓
Qwen 답변
```

Generation 관련 package import는 Backend 환경에서 Prompt Builder와 llama.cpp client를 사용할 때 불필요하게 GPU/PyTorch 관련 package 전체를 강제 import하지 않도록 정리되어 있다.

---

# 5. AWS Python 환경

현재 Python 환경은 Backend용과 AI/GPU용을 분리하여 사용한다.

## Backend Python 환경

경로:

```text
/home/ubuntu/ddokbot/venvs/one-cycle-backend
```

Python:

```text
/home/ubuntu/ddokbot/venvs/one-cycle-backend/bin/python
```

확인:

```bash
/home/ubuntu/ddokbot/venvs/one-cycle-backend/bin/python --version
```

주요 용도:

```text
FastAPI
SQLAlchemy
Alembic
PostgreSQL 접근
DB 적재
RAG Backend 코드
```

---

## AI / GPU Python 환경

경로:

```text
/home/ubuntu/ddokbot/venvs/one-cycle
```

Python:

```text
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python
```

확인:

```bash
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python --version
```

주요 용도:

```text
PyTorch
CUDA
FlagEmbedding
BGE-M3
GPU 기반 Embedding
```

GPU 환경 확인:

```bash
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python - <<'PY'
import torch

print("torch:", torch.__version__)
print("cuda:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
PY
```

현재 검증된 환경:

```text
GPU      NVIDIA L4
PyTorch  2.13.0+cu130
CUDA     True
```

GPU 전체 상태:

```bash
nvidia-smi
```

---

# 6. PostgreSQL + pgvector 서비스 DB

현재 MVP 통합에서 사용하는 DB Container:

```text
one-cycle-postgres
```

DB 구성:

```text
PostgreSQL : 16
pgvector   : 0.8.2
DB         : one_cycle
User       : one_cycle
Host       : 127.0.0.1
Host Port  : 5433
```

Docker Compose 파일:

```text
/home/ubuntu/ddokbot/one-cycle-integration/infra/docker-compose.yml
```

프로젝트 상대 경로:

```text
infra/docker-compose.yml
```

Docker Volume:

```text
one-cycle-postgres-data
```

DB는 AWS 외부 인터넷에 PostgreSQL 포트를 직접 공개하지 않고 localhost에 바인딩되어 있다.

팀원 모두 AWS SSH 접속이 가능하므로 AWS 서버에 접속한 뒤 동일한 DB를 직접 조회할 수 있다.

---

# 7. 서비스 DB와 테스트 DB 구분

AWS에는 DB 기술 검증 과정에서 사용한 별도 Container가 존재한다.

```text
one-cycle-db-test
```

현재 MVP 통합 데이터를 확인할 때 사용하는 서비스 DB는 다음 Container이다.

```text
one-cycle-postgres
```

즉 팀원은 두 DB를 혼동하지 않아야 한다.

```text
one-cycle-postgres  → 현재 MVP 통합 서비스 DB
one-cycle-db-test   → 별도 DB 기술 검증 환경
```

---

# 8. DB Container 확인

AWS에서:

```bash
docker ps --filter name=one-cycle-postgres
```

정상이라면 `one-cycle-postgres` Container가 실행 중이어야 한다.

전체 관련 Container를 보고 싶다면:

```bash
docker ps
```

---

# 9. PostgreSQL 직접 접속

AWS 내부에서:

```bash
docker exec -it one-cycle-postgres \
  psql -U one_cycle -d one_cycle
```

테이블 목록:

```sql
\dt
```

주요 테이블:

```text
system_state
collection_runs
announcements
documents
processing_runs
processing_artifacts
document_structures
key_information
chunk_sets
chunks
embeddings
admins
error_logs
alembic_version
```

psql 종료:

```sql
\q
```

---

# 10. 현재 DB 적재 결과

현재 `announcement_001` 1건을 기준으로 실제 통합 데이터를 저장해 두었다.

| 데이터 | 현재 건수 |
|---|---:|
| announcements | 1 |
| documents | 1 |
| document_structures | 1 |
| key_information | 1 |
| chunk_sets | 1 |
| chunks | 291 |
| embeddings | 291 |

한 번에 확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  (SELECT count(*) FROM announcements) AS announcements,
  (SELECT count(*) FROM documents) AS documents,
  (SELECT count(*) FROM document_structures) AS structures,
  (SELECT count(*) FROM key_information) AS key_information,
  (SELECT count(*) FROM chunk_sets) AS chunk_sets,
  (SELECT count(*) FROM chunks) AS chunks,
  (SELECT count(*) FROM embeddings) AS embeddings;
"
```

현재 정상 기준:

```text
announcements     1
documents         1
structures        1
key_information   1
chunk_sets        1
chunks          291
embeddings      291
```

위 결과가 나오면 현재 AWS에 적재한 대표 공고 데이터가 정상적으로 유지되고 있는 것이다.

---

# 11. DB-first 데이터 처리 기준

Structure 생성 이후의 후속 처리에서는 원본 HWP/HWPX를 계속 다시 읽지 않는다.

중간 데이터의 기준은 다음 DB 컬럼이다.

```text
document_structures.structure_json
```

전체 흐름:

```text
원본 HWP/HWPX
    ↓
Parser / Normalizer
    ↓
Structure JSON
    ↓
document_structures.structure_json
    ↓
Chunking
    ↓
chunks
    ↓
BGE-M3
    ↓
embeddings
    ↓
pgvector Retrieval
    ↓
RAG
```

따라서 Chunking 이후 기능을 구현하는 팀원은 DB에 저장된 Structure, Chunk, Embedding을 기준으로 후속 작업을 연결한다.

---

# 12. Structure 데이터 확인

Structure 기본 정보:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  document_id,
  processing_run_id,
  schema_version,
  jsonb_typeof(structure_json) AS structure_type
FROM document_structures;
"
```

Structure JSON 전체 확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT jsonb_pretty(structure_json)
FROM document_structures
WHERE id = 1;
"
```

Structure JSON 전체 출력은 양이 많으므로 필요한 경우에만 사용한다.

---

# 13. Chunk 데이터 확인

전체 Chunk 수:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT count(*) AS chunk_count
FROM chunks;
"
```

정상 기준:

```text
291
```

Chunk 유형별 개수:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  content_type,
  count(*)
FROM chunks
GROUP BY content_type
ORDER BY content_type;
"
```

현재 `announcement_001` Chunk 구성:

```text
intro             3
paragraph_group  36
paragraph_split   1
table_record     251

총 291
```

Chunk 내용 일부 확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  chunk_index,
  content_type,
  title,
  section_path,
  left(content, 300) AS content
FROM chunks
ORDER BY chunk_index
LIMIT 10;
"
```

---

# 14. 실제 신청자격 Chunk 확인

RAG 테스트에서 실제 검색 1위였던 `신청자격` Chunk를 직접 확인할 수 있다.

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  chunk_index,
  title,
  section_path,
  content
FROM chunks
WHERE title = '신청자격';
"
```

테스트 질문:

```text
신청 자격은 어떻게 되나요?
```

에 대해 해당 Chunk가 pgvector 검색 결과 1위로 검색되었다.

---

# 15. Embedding 데이터 확인

Embedding 개수 및 dimension:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  count(*) AS embeddings,
  min(dimension) AS min_dimension,
  max(dimension) AS max_dimension,
  count(DISTINCT chunk_id) AS unique_chunks
FROM embeddings;
"
```

현재 정상 기준:

```text
embeddings      291
min_dimension   1024
max_dimension   1024
unique_chunks   291
```

Embedding 처리 상태:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  status,
  count(*)
FROM embeddings
GROUP BY status;
"
```

정상 기준:

```text
completed  291
```

Embedding normalization 확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  normalized,
  count(*)
FROM embeddings
GROUP BY normalized;
"
```

정상 기준:

```text
true  291
```

Embedding이 없는 Chunk가 존재하는지 확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT count(*) AS chunks_without_embedding
FROM chunks c
LEFT JOIN embeddings e
  ON e.chunk_id = c.id
WHERE e.id IS NULL;
"
```

정상 기준:

```text
0
```

---

# 16. ProcessingRun 확인

현재 활성 ProcessingRun 확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  document_id,
  execution_status,
  verification_status,
  current_stage,
  is_active,
  activated_at
FROM processing_runs;
"
```

현재 대표 문서의 정상 상태:

```text
execution_status     succeeded
verification_status  pass
is_active            true
```

ProcessingRun은 `document_id`를 통해 Document와 연결된다.

필요하면 Announcement까지 같이 확인할 수 있다.

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  pr.id AS processing_run_id,
  pr.document_id,
  d.announcement_id,
  pr.execution_status,
  pr.verification_status,
  pr.is_active
FROM processing_runs pr
JOIN documents d
  ON d.id = pr.document_id;
"
```

---

# 17. ChunkSet 확인

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  processing_run_id,
  chunker_version,
  strategy,
  input_content_version,
  status,
  is_active,
  chunk_count
FROM chunk_sets;
"
```

현재 정상 기준:

```text
status       completed
is_active    true
chunk_count  291
```

---

# 18. Key Information 확인

현재 Key Information:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  announcement_id,
  source_processing_run_id,
  extraction_status,
  is_verified
FROM key_information;
"
```

현재 상태:

```text
extraction_status  completed
is_verified        false
```

## 중요

현재 `announcement_001`의 Key Information은 자동 추출 기능을 완전히 구현하여 생성한 최종 결과가 아니다.

기존 fixture/manual structured data를 실제 Announcement/ProcessingRun 구조와 연결하여 MVP 통합 테스트에 사용했다.

따라서 다음과 같이 이해해야 한다.

```text
Key Information DB 연결       완료
자동 Key Information 추출     추후 연결 필요
```

향후 자동 추출 기능을 구현할 때 현재 DB 스키마와 `source_processing_run_id` 연결 구조를 유지한 상태에서 자동 추출 결과로 교체한다.

---

# 19. pgvector Retrieval 기준

질의응답에서 전체 Embedding을 아무 조건 없이 검색하면 안 된다.

선택한 공고 범위를 기준으로 검색해야 한다.

기준 흐름:

```text
선택한 announcement_id
    ↓
해당 Document
    ↓
active + succeeded/pass ProcessingRun
    ↓
active + completed ChunkSet
    ↓
해당 Chunk
    ↓
completed Embedding
    ↓
pgvector Top-K
```

다른 공고의 Chunk가 검색 결과에 섞이면 안 된다.

현재 DB-first Retrieval 검증도 선택 공고 범위를 제한한 상태에서 수행했다.

---

# 20. 실제 pgvector Retrieval 검증 결과

테스트 질문:

```text
신청 자격은 어떻게 되나요?
```

BGE-M3로 질문을 1024차원 Vector로 생성한 뒤 PostgreSQL pgvector cosine similarity 검색을 수행했다.

Top-5 결과:

| 순위 | Chunk 제목 | Cosine Similarity |
|---:|---|---:|
| 1 | 신청자격 | 0.614604 |
| 2 | 계약 시 구비서류 | 0.559615 |
| 3 | 계약 시 구비서류 | 0.559109 |
| 4 | 계약 시 구비서류 | 0.539981 |
| 5 | 지구 및 단지 여건 등 | 0.534899 |

질문과 직접 관련된 `신청자격` Chunk가 1위로 검색되었다.

따라서 현재 대표 공고 기준 DB → BGE-M3 → pgvector Retrieval 흐름이 정상 동작하는 것을 확인했다.

---

# 21. llama.cpp 위치

llama.cpp 실행 파일:

```text
/home/ubuntu/tools/llama.cpp/build/bin/llama-server
```

사용 Qwen 모델:

```text
/home/ubuntu/ddokbot/models/llm/qwen/qwen2.5-7b-instruct-q4_k_m.gguf
```

모델:

```text
Qwen2.5-7B-Instruct
GGUF
Q4_K_M
```

llama.cpp API 주소:

```text
http://127.0.0.1:8080
```

---

# 22. llama.cpp 실행 여부 확인

8080 포트 확인:

```bash
ss -ltnp | grep ':8080'
```

Process 확인:

```bash
ps -ef | grep '[l]lama-server'
```

모델 API 확인:

```bash
curl -s http://127.0.0.1:8080/v1/models
```

정상이라면 Qwen GGUF 모델 정보가 반환된다.

---

# 23. llama.cpp 서버 실행 방법

서버가 실행 중이지 않을 경우 먼저 기존 8080 Process가 없는지 확인한다.

```bash
ss -ltnp | grep ':8080'
```

실행 중인 서버가 없다면 현재 검증한 설정은 다음과 같다.

```bash
nohup /home/ubuntu/tools/llama.cpp/build/bin/llama-server \
  -m /home/ubuntu/ddokbot/models/llm/qwen/qwen2.5-7b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  -ngl 999 \
  -np 1 \
  -fa on \
  > /tmp/one-cycle-llama-server.log 2>&1 &

echo $! > /tmp/one-cycle-llama-server.pid
```

로그 위치:

```text
/tmp/one-cycle-llama-server.log
```

로그 확인:

```bash
tail -50 /tmp/one-cycle-llama-server.log
```

PID 파일:

```text
/tmp/one-cycle-llama-server.pid
```

현재 llama.cpp는 영구 systemd 서비스로 등록한 상태가 아니라 수동 실행 기준이다.

따라서 AWS 서버 재부팅 또는 Process 종료 이후에는 llama.cpp가 실행 중인지 다시 확인해야 한다.

---

# 24. DB-first RAG Generation 검증 결과

실제 검증 질문:

```text
신청 자격은 어떻게 되나요?
```

검증 흐름:

```text
사용자 질문
    ↓
BGE-M3 Query Embedding
    ↓
PostgreSQL + pgvector
    ↓
선택 announcement 범위 제한
    ↓
Top-K Chunk
    ↓
Prompt Builder
    ↓
llama.cpp
    ↓
Qwen2.5-7B
    ↓
근거 기반 답변
```

실제 Qwen 답변에서는 다음 신청자격 정보가 생성되었다.

```text
만 19세 이상 성년자와 법인 신청 가능
외국인 신청 불가
주택 소유 여부와 관계없이 신청 가능
거주지역 제한 없음
소득·자산 요건 제한 없음
입주자저축 가입 여부와 관계없이 신청 가능
과거 당첨 사실 여부와 관계없이 신청 가능
```

답변에는 다음 근거 표시도 생성되었다.

```text
[근거 1]
```

최종 검증:

```text
answer_empty: False
source_markers: ['1']

DB-FIRST RAG GENERATION: PASS
```

따라서 현재 AWS에서는 다음 백엔드 AI 흐름까지 실제 검증된 상태이다.

```text
DB Structure
    ↓
Chunk
    ↓
Embedding
    ↓
pgvector Retrieval
    ↓
Prompt
    ↓
Qwen
    ↓
근거 기반 답변
```

---

# 25. 현재 RAG 테스트 실행 방식 주의

현재 DB-first Retrieval → Prompt → Qwen 전체 검증은 AWS 터미널에서 Python 코드로 직접 실행하여 성공 여부를 확인한 상태이다.

즉 다음 구성 요소는 각각 존재한다.

```text
Structure DB 적재 코드
Chunk DB 적재 코드
Embedding DB 적재 코드
Retrieval 코드
Generation 코드
llama.cpp
Qwen 모델
```

하지만 현재 팀원이 다음처럼 명령 하나만 실행해서 전체 RAG를 다시 수행하는 전용 실행 파일이 완성된 상태는 아니다.

```text
python backend/scripts/run_db_rag.py
```

위와 같은 단일 DB-first RAG 실행 파일이 현재 MVP의 최종 실행 방식은 아니다.

다음 작업에서 이 검증 흐름을 **FastAPI 질의응답 API 내부에 연결하는 것이 실제 목표**이다.

---

# 26. `/tmp` 파일 주의

검증 과정에서 다음과 같은 임시 경로가 사용되었다.

```text
/tmp/one-cycle-db-first/
/tmp/one-cycle-llama-server.log
/tmp/one-cycle-llama-server.pid
```

이 파일들은 서비스 데이터의 Source of Truth가 아니다.

DB-first 구조에서 영구적으로 확인해야 할 주요 데이터는 PostgreSQL의 다음 테이블이다.

```text
document_structures
chunks
embeddings
```

`/tmp` 아래의 파일은 테스트 과정에서 생성된 임시 산출물이므로 후속 기능이 해당 파일에 의존하도록 구현하면 안 된다.

---

# 27. 현재 SystemState

현재 공식 서비스 Collection은 아직 활성화하지 않았다.

확인:

```bash
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  id,
  active_collection_run_id,
  updated_at
FROM system_state;
"
```

현재 기준:

```text
active_collection_run_id = NULL
```

이유:

```text
DB 적재                완료
Chunk / Embedding       완료
pgvector Retrieval      완료
Qwen Generation         완료

FastAPI 전체 연결       미완료
React 연결              미완료
브라우저 전체 E2E       미완료
```

따라서 일부만 준비된 Collection을 공식 서비스 데이터로 노출하지 않은 상태이다.

FastAPI → React까지 전체 MVP 검증이 끝난 뒤 Active Collection을 설정한다.

---

# 28. 팀원이 AWS 접속 후 가장 먼저 확인할 순서

AWS에 접속한 팀원은 아래 순서로 현재 환경을 확인하면 된다.

```bash
# 1. 통합 작업 디렉터리 이동
cd /home/ubuntu/ddokbot/one-cycle-integration


# 2. 원격 feature/rag 확인
git fetch origin feature/rag
git log --oneline origin/feature/rag -5


# 3. 서비스 DB Container 확인
docker ps --filter name=one-cycle-postgres


# 4. DB 데이터 수 확인
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  (SELECT count(*) FROM announcements) AS announcements,
  (SELECT count(*) FROM document_structures) AS structures,
  (SELECT count(*) FROM chunks) AS chunks,
  (SELECT count(*) FROM embeddings) AS embeddings;
"


# 5. 신청자격 Chunk 확인
docker exec one-cycle-postgres \
  psql -U one_cycle -d one_cycle \
  -c "
SELECT
  chunk_index,
  title,
  section_path,
  content
FROM chunks
WHERE title = '신청자격';
"


# 6. llama.cpp 실행 여부 확인
ss -ltnp | grep ':8080'


# 7. Qwen API 확인
curl -s http://127.0.0.1:8080/v1/models


# 8. GPU 확인
nvidia-smi
```

정상 기준:

```text
announcement     1
structure        1
chunks         291
embeddings     291

신청자격 Chunk 조회 가능
llama.cpp :8080 응답
Qwen model API 응답
NVIDIA L4 확인
```

여기까지 정상이라면 현재 AWS 통합 환경과 DB 데이터가 유지되고 있다고 판단하면 된다.

---

# 29. 현재까지 완료된 MVP 통합 범위

현재 완료:

```text
HWP/HWPX 문서 처리 기반
    ↓
Structure 생성
    ↓
Structure DB 저장
    ↓
DB Structure 기반 Chunk 생성
    ↓
Chunk DB 저장
    ↓
BGE-M3 Embedding
    ↓
Embedding DB 저장
    ↓
pgvector Retrieval
    ↓
Qwen Generation
    ↓
근거 표시
```

대표 공고:

```text
announcement_001
```

현재 적재 결과:

```text
Structure      1
Chunk        291
Embedding    291
```

---

# 30. 다음 작업: FastAPI RAG 연결

현재 가장 먼저 이어서 해야 할 작업이다.

터미널에서 검증한:

```text
질문
    ↓
BGE-M3
    ↓
pgvector
    ↓
Top-K Chunk
    ↓
Prompt
    ↓
Qwen
```

흐름을 FastAPI 질의응답 Endpoint에서 실행하도록 연결한다.

API 입력에서 최소한 다음 값이 필요하다.

```text
announcement_id
question
```

응답에는 최소 다음 값이 필요하다.

```text
answer
sources
```

FastAPI 내부 처리 흐름:

```text
POST 질문
    ↓
announcement_id 확인
    ↓
선택 공고의 활성 데이터 확인
    ↓
질문 BGE-M3 Embedding
    ↓
해당 공고의 Chunk만 pgvector 검색
    ↓
Top-K 근거
    ↓
Prompt 생성
    ↓
llama.cpp 호출
    ↓
answer + sources 반환
```

반드시 지켜야 하는 조건:

```text
선택 공고 범위 제한
답변 근거 반환
근거 부족 처리
```

---

# 31. 다음 작업: Query Embedding 실행 연결

현재 Backend Python 환경과 AI/GPU Python 환경이 분리되어 있다.

```text
Backend
/home/ubuntu/ddokbot/venvs/one-cycle-backend

AI / GPU
/home/ubuntu/ddokbot/venvs/one-cycle
```

따라서 FastAPI에서 사용자 질문을 받을 때 BGE-M3 Query Embedding을 어떤 방식으로 호출할지 실제 서비스 실행 구조를 확정해야 한다.

현재 검증 과정에서는 AI 환경에서 BGE-M3를 실행하고, Backend 환경에서 DB와 Generation을 연결했다.

후속 작업에서는 기존 프로젝트 구조를 확인한 뒤 이 두 환경을 무작정 합치거나 Backend venv에 GPU package를 추가하기보다, 기존 Embedding 실행 구조와 FastAPI 연결 방식을 기준으로 구현한다.

---

# 32. 다음 작업: 공고 상세와 RAG 연결

사용자가 화면에서 선택한 공고가 RAG 검색 범위와 동일하게 연결되어야 한다.

```text
공고 목록
    ↓
공고 상세
    ↓
announcement_id
    ↓
질문 입력
    ↓
FastAPI
    ↓
해당 announcement_id 데이터만 Retrieval
```

다른 공고의 Chunk가 섞이면 안 된다.

---

# 33. 다음 작업: 근거 부족 처리

문서에 충분한 근거가 없는 질문에 대해 모델이 임의로 답변하지 않도록 한다.

현재 Prompt 기준 근거 부족 응답:

```text
제공된 LH 공고문 근거에서 확인할 수 없습니다.
```

FastAPI에서도 동일한 정책이 유지되어야 한다.

확인해야 하는 상황:

```text
검색 결과 없음
검색 근거 부족
질문과 관련 없는 Chunk만 검색됨
문서에 없는 정보 질문
```

이 경우 일반 지식으로 보충하여 답변하지 않는 것이 MVP 기준이다.

---

# 34. 다음 작업: React 연결

FastAPI RAG Endpoint가 완성되면 Frontend를 연결한다.

흐름:

```text
공고 상세 페이지
    ↓
사용자 질문 입력
    ↓
announcement_id + question
    ↓
FastAPI
    ↓
answer + sources
    ↓
답변 표시
    ↓
근거 표시
```

현재 MVP는 채팅 기록 저장 기능을 사용하지 않는다.

따라서 질의응답은 현재 선택한 공고와 현재 질문을 기준으로 동작한다.

---

# 35. 다음 작업: 전체 MVP E2E 검증

FastAPI와 React 연결 이후 브라우저에서 실제 서비스 흐름을 확인한다.

최소 확인 질문 유형:

```text
신청 일정
신청 자격
제출 서류
공급 정보
표에 포함된 정보
문서에 존재하지 않는 정보
```

확인 항목:

```text
공고 선택이 정상적으로 전달되는가
해당 공고 Chunk만 검색되는가
답변이 생성되는가
근거가 함께 표시되는가
표 기반 정보도 검색되는가
근거가 없을 때 임의 생성하지 않는가
응답 시간이 MVP 목표 범위 안인가
```

전체 검증을 통과한 후 `system_state.active_collection_run_id`를 실제 서비스 Collection으로 활성화한다.

---

# 36. HWP/HWPX 관련 기준

전체 MVP의 문서 지원 범위에는 HWP와 HWPX가 모두 포함된다.

현재 `announcement_001`은 첫 번째 전체 DB-first E2E 대표 문서로 사용한 HWPX 문서이다.

기존 문서 처리 검증에서는 HWP와 HWPX 모두 Parser → Normalizer → Structure 단계의 실행 가능 여부를 확인했다.

따라서 `announcement_001` 1건의 E2E 성공을 전체 HWP/HWPX 문서 지원 완료와 동일하게 해석하지 않는다.

다른 HWP/HWPX 문서는 문서 처리 및 회귀 검증 자료로 계속 사용한다.

---

# 37. MVP에서 현재 제외할 작업

현재는 MVP 완성에 집중한다.

다음 고도화 기능은 현재 실제 서비스 실행 경로에 추가하지 않는다.

```text
Reranker
Hybrid Search
자동 평가 시스템
다중 문서 RAG
추가 검색 알고리즘 튜닝
```

현재 MVP RAG 기준:

```text
BGE-M3
    ↓
pgvector Top-K
    ↓
Qwen
```

이 흐름으로 먼저 FastAPI와 Frontend까지 완성한다.

---

# 38. 팀원 인수인계 요약

## 어디에서 확인하는가

AWS 통합 검증 디렉터리:

```text
/home/ubuntu/ddokbot/one-cycle-integration
```

Git 기준:

```text
feature/rag
```

서비스 DB:

```text
one-cycle-postgres
```

Backend Python:

```text
/home/ubuntu/ddokbot/venvs/one-cycle-backend
```

AI/GPU Python:

```text
/home/ubuntu/ddokbot/venvs/one-cycle
```

llama.cpp:

```text
/home/ubuntu/tools/llama.cpp/build/bin/llama-server
```

Qwen 모델:

```text
/home/ubuntu/ddokbot/models/llm/qwen/qwen2.5-7b-instruct-q4_k_m.gguf
```

---

## 무엇이 준비되어 있는가

```text
announcement       1
document           1
structure          1
key_information    1
chunk_set          1
chunks           291
embeddings       291
```

---

## 어디까지 검증되었는가

```text
Structure DB 저장
    ↓
Chunk DB 저장
    ↓
Embedding DB 저장
    ↓
BGE-M3 Query Embedding
    ↓
pgvector Retrieval
    ↓
Prompt
    ↓
llama.cpp / Qwen
    ↓
근거 기반 답변
```

검증 질문:

```text
신청 자격은 어떻게 되나요?
```

결과:

```text
신청자격 Chunk 검색 1위
Qwen 답변 생성
[근거 1] 표시
DB-FIRST RAG GENERATION PASS
```

---

## 여기서부터 무엇을 하면 되는가

```text
현재 DB-first RAG 흐름
    ↓
FastAPI 질의응답 Endpoint 연결
    ↓
Query Embedding 실행 구조 연결
    ↓
선택 공고 범위 Retrieval
    ↓
근거 부족 처리
    ↓
공고 상세와 announcement_id 연결
    ↓
React 질의응답 UI 연결
    ↓
브라우저 전체 MVP E2E
    ↓
SystemState Active Collection 설정
```

현재 AWS DB와 `feature/rag`를 기준으로 후속 MVP 개발을 이어간다.