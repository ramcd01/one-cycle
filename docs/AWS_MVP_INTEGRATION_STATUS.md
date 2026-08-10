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
  /home/ubuntu/ddokbot/venvs/one-cycle/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18000

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
