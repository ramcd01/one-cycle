# 협업 규칙

## 1. 브랜치 구성

```text
main
└─ develop
   ├─ feature/frontend
   ├─ feature/backend-infra
   ├─ feature/document-processing
   └─ feature/rag
```

- `main`: 최종 제출 및 배포
- `develop`: 전체 기능 통합
- `feature/frontend`: 프론트엔드 개발
- `feature/backend-infra`: 백엔드 및 인프라 개발
- `feature/document-processing`: 문서 처리 개발
- `feature/rag`: 임베딩 및 RAG 개발

각 팀원은 담당 브랜치에서 작업하고 `develop` 브랜치로 Pull Request를 생성합니다.

## 2. 작업 흐름

```text
담당 브랜치에서 개발
→ 로컬 실행 및 테스트
→ develop으로 Pull Request 생성
→ 변경 내용 검토
→ develop에 병합
→ 전체 기능 통합 테스트
→ main에 최종 병합
```

## 3. 담당 영역

### Frontend

담당 브랜치:

```text
feature/frontend
```

주요 경로:

```text
frontend/
```

주요 작업:

- 사용자 화면
- 관리자 화면
- 공고 목록 및 상세 화면
- AI 질의응답 화면
- PC·모바일 반응형 UI
- 백엔드 API 연결

### Backend 및 Infra

담당 브랜치:

```text
feature/backend-infra
```

주요 경로:

```text
backend/
infra/
```

주요 작업:

- FastAPI 백엔드 구성
- 백엔드 API 구현
- PostgreSQL 연결
- 데이터베이스 구조 설계
- Docker 및 pgvector 환경 구성
- CI/CD 및 배포 설정

### Document Processing

담당 브랜치:

```text
feature/document-processing
```

주요 경로:

```text
crawler/
parser/
normalizer/
structure/
chunking/
test_documents/
```

주요 작업:

- LH 공고 수집
- HWP/HWPX 첨부파일 다운로드
- 문서 유효성 확인
- HWP/HWPX 문서 파싱
- 파싱 결과 정규화
- 공통 문서 구조 생성
- 검색용 Chunk 생성
- 테스트 문서 및 처리 결과 검증

### RAG

담당 브랜치:

```text
feature/rag
```

주요 경로:

```text
embedding/
rag/
```

주요 작업:

- Chunk 임베딩 생성
- 임베딩 벡터 저장
- 유사 문서 검색
- 검색 결과 Reranking
- LLM 답변 생성
- 답변 근거 제공
- RAG 성능 평가

## 4. 공통 경로 관리

다음 경로와 파일은 여러 기능에서 함께 사용할 수 있습니다.

```text
.github/
config/
scripts/
tests/
docs/
requirements.txt
.env.example
.gitignore
README.md
CONTRIBUTING.md
run_pipeline.py
```

공통 항목을 수정할 때는 팀원에게 변경 내용을 공유합니다.

Pull Request에는 수정한 공통 파일과 수정 이유를 작성합니다.

## 5. 테스트 문서 관리

테스트 문서는 파일 확장자가 아니라 공고 단위로 관리합니다.

```text
test_documents/
├─ announcement_001/
├─ announcement_002/
└─ announcement_003/
```

각 공고 폴더에는 해당 공고의 원문과 처리 결과 검증에 필요한 자료를 함께 관리합니다.

개인정보가 포함되거나 외부 공개가 제한된 문서는 업로드하지 않습니다.

## 6. 파일 업로드 규칙

다음 항목은 GitHub에 업로드하지 않습니다.

- 실제 환경변수가 들어 있는 `.env`
- 비밀번호 및 API Key
- Python 가상환경
- `node_modules`
- 실행 결과물
- 로그 및 임시 파일
- 임베딩 파일
- AI 모델 파일
- 개인정보가 포함된 문서
- 외부 공개가 제한된 문서

## 7. Pull Request 작성

Pull Request에는 다음 내용을 작성합니다.

- 작업 목적
- 변경한 내용
- 실행 또는 테스트 방법
- 테스트 결과
- 다른 영역에 미치는 영향
- 추가 확인 사항

## 8. 병합 기준

다음 조건을 확인한 뒤 `develop`에 병합합니다.

- 담당 기능이 정상적으로 실행됨
- 필요한 테스트를 수행함
- 실제 비밀번호나 불필요한 파일이 포함되지 않음
- 다른 담당 영역의 파일을 임의로 삭제하지 않음
- 공통 파일 수정 내용을 팀에 공유함
- 다른 기능에 미치는 영향을 Pull Request에 작성함