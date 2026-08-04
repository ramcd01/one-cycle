\# One Cycle



LH 공고문과 HWP/HWPX 문서를 기반으로 핵심 정보를 제공하고, 문서 근거를 활용한 AI 질의응답을 지원하는 서비스입니다.



\## 프로젝트 구조



```text

one-cycle/

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

├─ tests/                   # 백엔드·문서 처리·RAG 테스트

├─ test\_documents/          # 문서 처리 검증용 테스트 문서

├─ infra/                   # Docker·DB·배포 환경

├─ config/                  # 공통 설정

├─ scripts/                 # 실행 및 관리 스크립트

├─ docs/                    # 프로젝트 문서

├─ .env.example             # 환경변수 예시

├─ .gitignore               # Git 제외 파일 설정

├─ CONTRIBUTING.md          # 협업 규칙

├─ README.md                # 프로젝트 안내

├─ requirements.txt         # Python 패키지 목록

└─ run\_pipeline.py          # 전체 문서 처리 흐름 실행 파일

```



\## 브랜치 구조



```text

main

└─ develop

&#x20;  ├─ feature/frontend

&#x20;  ├─ feature/backend-infra

&#x20;  ├─ feature/document-processing

&#x20;  └─ feature/rag

```



\### 브랜치 역할



\- `main`: 최종 제출 및 배포용 브랜치

\- `develop`: 전체 기능 통합용 브랜치

\- `feature/frontend`: 프론트엔드 개발

\- `feature/backend-infra`: 백엔드, DB, Docker, CI/CD 개발

\- `feature/document-processing`: 수집, 파싱, 정규화, 구조화, Chunking 개발

\- `feature/rag`: 임베딩, 검색, Reranker, 답변 생성 개발



\## 환경변수 설정



실제 환경변수 파일인 `.env`는 GitHub에 포함하지 않습니다.



프로젝트를 처음 실행할 때 `.env.example`을 복사하여 `.env` 파일을 생성합니다.



```cmd

copy .env.example .env

```



생성한 `.env`에는 각자의 로컬 환경에 맞는 값을 입력합니다.



\## 주의사항



\- 실제 비밀번호가 포함된 `.env`는 GitHub에 업로드하지 않습니다.

\- 비밀번호와 API Key를 코드에 직접 작성하지 않습니다.

\- 개인정보나 외부 공개가 제한된 문서는 업로드하지 않습니다.

\- 가상환경, 실행 결과물, 모델 파일은 GitHub에 업로드하지 않습니다.

\- 공통 파일을 수정할 때는 팀원에게 먼저 공유합니다.

