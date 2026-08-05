# One Cycle

LH 공고문과 HWP/HWPX 문서를 기반으로 핵심 정보를 제공하고, 문서 원문을 근거로 AI 질의응답을 지원하는 서비스입니다.

## 프로젝트 구조

```text
one-cycle/
├─ .github/                 # GitHub Actions 및 협업 설정
├─ backend/                 # FastAPI 백엔드
├─ frontend/                # 사용자·관리자 웹 화면
├─ crawler/                 # LH 공고 및 첨부파일 수집
├─ parser/                  # HWP/HWPX 문서 파싱
│  └─ libs/                 # 문서 파싱용 외부 라이브러리
├─ normalizer/              # 파싱 결과 정규화
├─ structure/               # 문서 공통 구조 생성
├─ chunking/                # 검색용 Chunk 생성
├─ embedding/               # 임베딩 생성
├─ rag/                     # 검색·Reranker·답변 생성
├─ config/                  # 문서 처리 및 RAG 공통 설정
├─ scripts/                 # 실행·점검·관리용 스크립트
├─ tests/                   # 프로젝트 테스트 코드
├─ test_documents/          # 문서 처리 검증용 자료
│  └─ announcement_001/     # 공고 단위 테스트 데이터
├─ infra/                   # Docker·DB·배포 환경
│  └─ postgres/
│     └─ init/
├─ docs/                    # 프로젝트 문서
├─ .env.example             # 환경변수 예시
├─ .gitignore               # Git 제외 파일 설정
├─ CONTRIBUTING.md          # 협업 규칙
├─ README.md                # 프로젝트 안내
├─ requirements.txt         # Python 패키지 목록
└─ run_pipeline.py          # 전체 문서 처리 파이프라인 실행 파일
```

## 브랜치 구조

```text
main
└─ develop
   ├─ feature/frontend
   ├─ feature/backend-infra
   ├─ feature/document-processing
   └─ feature/rag
```

## 브랜치 역할

- `main`: 최종 제출 및 배포용 브랜치
- `develop`: 전체 기능 통합용 브랜치
- `feature/frontend`: 사용자·관리자 웹 화면 개발
- `feature/backend-infra`: FastAPI, 데이터베이스, Docker 및 배포 환경 개발
- `feature/document-processing`: 공고 수집, 문서 파싱, 정규화, 구조화 및 Chunking 개발
- `feature/rag`: 임베딩, 검색, Reranker 및 답변 생성 개발

## 담당 영역

```text
feature/frontend
└─ frontend/

feature/backend-infra
├─ backend/
└─ infra/

feature/document-processing
├─ crawler/
├─ parser/
├─ normalizer/
├─ structure/
├─ chunking/
└─ test_documents/

feature/rag
├─ embedding/
└─ rag/
```

`config/`, `scripts/`, `tests/`, `docs/`는 여러 기능에서 사용할 수 있는 공통 경로입니다.

## 테스트 문서 관리

테스트 문서는 공고 단위로 구분합니다.

```text
test_documents/
├─ announcement_001/
├─ announcement_002/
└─ announcement_003/
```

각 공고 폴더에는 해당 공고의 원문 문서와 문서 처리 검증에 필요한 자료를 함께 관리합니다.

개인정보가 포함되거나 외부 공개가 제한된 문서는 GitHub에 업로드하지 않습니다.

## 환경변수 설정

실제 환경변수 파일인 `.env`는 GitHub에 포함하지 않습니다.

프로젝트를 처음 실행할 때 `.env.example`을 복사하여 `.env`를 생성합니다.

```cmd
copy .env.example .env
```

생성한 `.env`에는 각자의 로컬 환경에 맞는 값을 입력합니다.

## 주의사항

- 실제 비밀번호가 포함된 `.env`는 GitHub에 업로드하지 않습니다.
- 비밀번호와 API Key를 코드에 직접 작성하지 않습니다.
- Python 가상환경과 `node_modules`는 업로드하지 않습니다.
- 실행 결과물, 임베딩 파일, 모델 파일은 업로드하지 않습니다.
- 개인정보나 외부 공개가 제한된 문서는 업로드하지 않습니다.
- 공통 파일을 수정할 때는 팀원에게 변경 내용을 공유합니다.