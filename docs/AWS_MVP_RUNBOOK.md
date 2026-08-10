# AWS MVP 실행 및 재현 가이드

작성일: 2026-08-10  
대상 브랜치: `share/aws-mvp-integration-20260810`

이 문서는 AWS 공용 서버에서 검증한 MVP 통합 환경을 팀원이 동일하게 재현하고 확인하기 위한 실행 가이드이다.

실행 순서는 다음과 같다.

```text
공유 브랜치 준비
→ .env 준비
→ PostgreSQL 확인
→ llama.cpp 확인
→ FastAPI 실행
→ 사용자 Frontend 실행
→ 관리자 Frontend 실행
→ SSH Tunnel 연결
→ API / 브라우저 E2E 확인
```

## 1. 기준 환경

현재 검증 기준은 다음과 같다.

| 구성 | 기준 |
| --- | --- |
| 작업 저장소 | `/home/ubuntu/ddokbot/one-cycle-integration` |
| Python 환경 | `/home/ubuntu/ddokbot/venvs/one-cycle` |
| PostgreSQL | `127.0.0.1:5432` |
| 서비스 DB | `one_cycle` |
| DB 컨테이너 | `one-cycle-postgres` |
| Embedding | `BAAI/bge-m3` |
| llama.cpp | `127.0.0.1:8080` |
| LLM | `qwen2.5-7b-instruct` |
| FastAPI | `127.0.0.1:18000` |
| 사용자 Frontend | `0.0.0.0:5173` |
| 관리자 Frontend | `127.0.0.1:5500` |

`one-cycle-db-test`는 연결 검증용 별도 테스트 DB이며 현재 서비스 DB가 아니다.

---

## 2. 공유 브랜치 준비

기존 저장소에서 브랜치를 확인하려면:

```bash
cd /home/ubuntu/ddokbot/one-cycle-integration
git fetch origin
git branch --show-current
```

공유 브랜치:

```text
share/aws-mvp-integration-20260810
```

새 worktree가 필요한 경우에는 기존 공용 작업 디렉터리를 덮어쓰지 말고 별도 경로를 사용한다.

예:

```bash
cd /home/ubuntu/ddokbot/one-cycle
git fetch origin

git worktree add \
  /home/ubuntu/ddokbot/one-cycle-mvp-share \
  origin/share/aws-mvp-integration-20260810
```

기존 AWS 작업 디렉터리에 대해 `reset --hard`, `clean -fd`, 강제 checkout을 수행하지 않는다.

---

## 3. Python / GPU 환경 확인

현재 통합 검증에 사용한 Python 환경:

```text
/home/ubuntu/ddokbot/venvs/one-cycle
```

확인:

```bash
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python --version
```

이 환경은 현재 RAG/LLM 통합 검증에 사용 중이므로 임의로 삭제하거나 새로 덮어쓰지 않는다.

---

## 4. `.env` 준비

실제 `.env`는 Git에 커밋하지 않는다.

저장소의 `.env.example`에는 현재 검증 환경에서 사용하는 모든 환경변수 이름과 비민감 설정값이 기록되어 있다.

현재 비민감 기준값:

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=one_cycle
POSTGRES_USER=one_cycle

EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_USE_FP16=true
EMBEDDING_REQUIRE_CUDA=true
EMBEDDING_DEVICE_INDEX=0

LLAMA_BASE_URL=http://127.0.0.1:8080
LLAMA_MODEL=qwen2.5-7b-instruct
LLAMA_API_KEY=
LLAMA_TIMEOUT_SECONDS=600

RAG_ANSWER_FUNCTION=rag.service:answer_question
MVP_ANNOUNCEMENT_ID=1
MVP_ANNOUNCEMENT_DIRECTORY=announcement_001
MVP_DOCUMENT_FORMAT=hwpx

ADMIN_ID=admin
```

비밀값이 필요한 항목:

```text
POSTGRES_PASSWORD
ADMIN_PASSWORD
ADMIN_JWT_SECRET
```

이 값들은 GitHub에 올리지 않고 팀 내부의 안전한 방식으로 전달한다.

### 같은 AWS 서버의 기존 검증 환경을 그대로 사용하는 경우

새 worktree에서 기존 검증용 `.env`를 재사용하려면 서버 내부에서 복사한다.

```bash
cp \
  /home/ubuntu/ddokbot/one-cycle-integration/.env \
  /새로운/작업경로/.env

chmod 600 /새로운/작업경로/.env
```

### 새 `.env`를 만드는 경우

```bash
cp .env.example .env
chmod 600 .env
```

그 후 `<SET_ON_SERVER>` 부분만 실제 비밀값으로 설정한다.

FastAPI 실행 전 `.env`를 현재 shell 환경에 export한다.

```bash
set -a
source .env
set +a
```

---

## 5. PostgreSQL 서비스 DB 확인

서비스 DB 컨테이너:

```text
one-cycle-postgres
```

확인:

```bash
docker ps \
  --filter name=one-cycle-postgres \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

DB 준비 상태 확인:

```bash
docker exec one-cycle-postgres \
  pg_isready \
  -U one_cycle \
  -d one_cycle
```

정상 기준:

```text
accepting connections
```

현재 서비스 포트 확인:

```bash
ss -ltnp | grep ':5432'
```

현재 서비스 DB 및 named volume을 임의로 삭제하거나 초기화하지 않는다.

---

## 6. llama.cpp / Qwen 확인

현재 llama-server 실행 파일:

```text
/home/ubuntu/tools/llama.cpp/build/bin/llama-server
```

현재 GGUF 모델:

```text
/home/ubuntu/ddokbot/models/llm/qwen/qwen2.5-7b-instruct-q4_k_m.gguf
```

먼저 이미 실행 중인지 확인한다.

```bash
ss -ltnp | grep ':8080'
```

또는:

```bash
ps -ef \
  | grep llama-server \
  | grep -v grep
```

이미 `127.0.0.1:8080`에서 실행 중이면 새 프로세스를 추가로 띄우지 않는다.

실행 중이지 않을 때 현재 검증 기준 명령:

```bash
/home/ubuntu/tools/llama.cpp/build/bin/llama-server \
  -m /home/ubuntu/ddokbot/models/llm/qwen/qwen2.5-7b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  -ngl 999 \
  -np 1 \
  -fa on
```

---

## 7. FastAPI 실행

작업 경로로 이동:

```bash
cd /home/ubuntu/ddokbot/one-cycle-integration
```

환경변수 적용:

```bash
set -a
source .env
set +a
```

실행:

```bash
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python \
  -m uvicorn backend.app.main:app \
  --host 127.0.0.1 \
  --port 18000
```

이미 실행 중인지 확인:

```bash
ss -ltnp | grep ':18000'
```

정상 기준은 `127.0.0.1:18000` LISTEN이다.

---

## 8. 사용자 Frontend 실행

```bash
cd /home/ubuntu/ddokbot/one-cycle-integration/frontend/user
```

`node_modules`가 없는 경우:

```bash
npm ci
```

실행:

```bash
npm run dev -- --host 0.0.0.0
```

확인:

```bash
ss -ltnp | grep ':5173'
```

현재 검증 기준 포트는 `5173`이다.

---

## 9. 관리자 Frontend 실행

```bash
cd /home/ubuntu/ddokbot/one-cycle-integration/frontend/admin
```

실행:

```bash
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python \
  serve_admin.py \
  --host 127.0.0.1 \
  --port 5500 \
  --api http://127.0.0.1:18000
```

확인:

```bash
ss -ltnp | grep ':5500'
```

관리자 Frontend의 `/api/*` 요청은 FastAPI `127.0.0.1:18000`으로 proxy된다.

---

## 10. 전체 서비스 포트 확인

```bash
sudo ss -ltnp \
  | grep -E ':(5432|8080|18000|5173|5500)\b'
```

정상 구성:

```text
5432   PostgreSQL
8080   llama.cpp
18000  FastAPI
5173   사용자 Frontend
5500   관리자 Frontend
```

---

## 11. 로컬 PC에서 SSH Tunnel 연결

AWS IP와 PEM Key 정보는 Git에 기록하지 않는다.

사용자와 관리자 화면을 한 번에 연결하려면 로컬 PC에서:

```bash
ssh \
  -i <PEM_KEY_PATH> \
  -L 55173:127.0.0.1:5173 \
  -L 55174:127.0.0.1:5500 \
  ubuntu@<AWS_PUBLIC_IP>
```

브라우저 접속:

```text
사용자: http://localhost:55173
관리자: http://localhost:55174
```

---

## 12. API 정상 동작 확인

### 공고 목록

```bash
curl -sS \
  http://127.0.0.1:18000/api/announcements
```

현재 fixture 공고 1건이 반환되면 정상이다.

### 공고 상세

```bash
curl -sS \
  http://127.0.0.1:18000/api/announcements/1
```

정상 응답에서 확인할 주요 항목:

```text
id
title
documents
keyInformation
```

### RAG Chat

```bash
curl -sS \
  -X POST \
  http://127.0.0.1:18000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "announcementId": 1,
    "question": "접수 마감일이 언제까지야?"
  }'
```

정상 기준:

```text
AI 답변
+
evidence
```

---

## 13. 사용자 Frontend E2E 확인

브라우저에서 다음 순서로 확인한다.

```text
공고 목록
→ 공고 상세
→ 질문 입력
→ AI 답변 출력
→ 근거 문단 보기
```

현재 확인 완료:

- DB 공고 목록 출력
- 실제 `/api/chat` 호출
- AI 답변 출력
- evidence 출력
- 근거 모달 출력

현재 미완료:

- `DetailScreen.tsx` 상세 API 필드 매핑
- `keyInformation` 기반 핵심 정보 카드
- `requiredDocuments` 기반 제출 서류
- `상세 서류 보기` 실제 데이터 연결
- 목록/상세 화면의 시연용 fallback 제거

---

## 14. 관리자 Frontend 확인

브라우저에서 다음을 확인한다.

```text
관리자 로그인
→ 공고 관리
→ 공고 상세
→ 문서 관리
→ 오류 관리
```

현재 검증 완료:

- 관리자 로그인
- 공고 목록 조회
- 공고 상세 모달
- 문서 목록 조회
- 오류 목록 조회

수집, 재처리, retry 등 DB 상태를 변경하는 기능은 공용 환경에서 임의로 실행하지 않는다.

---

## 15. 현재 이어서 개발할 위치

사용자 Frontend 상세 화면 연결을 우선한다.

```text
frontend/user/src/components/screens/DetailScreen.tsx
```

우선순위:

1. API의 `announcementDate`, `publicationStatus` 필드를 실제 화면에 연결
2. `keyInformation.applicationPeriod` 연결
3. `keyInformation.supplyInformation` 연결
4. `keyInformation.eligibility` 연결
5. `keyInformation.incomeAssetCriteria` 연결
6. `keyInformation.requiredDocuments` 연결
7. 시연용 fallback / 하드코딩 제거
8. 사용자 페이지 전체 E2E 재검증

현재 단계에서는 새로운 검색 구조나 추가 RAG 기능보다 이미 연결된 DB/API 데이터를 Frontend에 정확히 표시하는 작업을 우선한다.

---

## 16. 공용 AWS 환경 주의사항

다음 항목은 임의로 삭제하거나 초기화하지 않는다.

```text
one-cycle-postgres
one-cycle-postgres-data
/home/ubuntu/ddokbot/venvs/one-cycle
/home/ubuntu/tools/llama.cpp
/home/ubuntu/ddokbot/models/llm/
```

다음 민감정보는 GitHub에 커밋하지 않는다.

```text
.env
POSTGRES_PASSWORD
ADMIN_PASSWORD
ADMIN_JWT_SECRET
PEM Key
AWS 접속정보
```

공유 브랜치는 현재 검증된 AWS MVP 통합 상태를 보존하기 위한 브랜치이며, 기존 개발 브랜치를 강제로 덮어쓰기 위한 브랜치가 아니다.
