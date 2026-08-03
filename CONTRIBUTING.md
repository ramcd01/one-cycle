# GitHub 협업 규칙

## 브랜치 구성

- `main`: 발표·배포 가능한 안정 버전
- `develop`: 팀 개발 결과 통합 브랜치
- `feature/backend-foundation`: FastAPI 기본 구조와 공통 백엔드 설정
- `feature/db-pgvector`: PostgreSQL, pgvector, SQLAlchemy, Alembic 구성
- `feature/file-upload`: HWP/HWPX 업로드와 문서 등록 API
- `feature/chat-session`: 채팅 세션, 질문·답변, 근거 저장 API
- `feature/frontend-user`: 일반 사용자 화면
- `feature/frontend-admin`: 관리자 화면
- `feature/rag-reranker-integration`: RAG Reranker 통합
- `feature/ci-pipeline`: GitHub Actions CI 구성
- `feature/cd-deployment`: AWS 배포 환경 구성

`parsing_test`, `structure-test`는 기존 실험 기록용이며 신규 개발에는 사용하지 않습니다.

## 기본 규칙

- `main`과 `develop`에서 직접 개발하거나 Push하지 않습니다.
- 각 담당자는 지정된 `feature/*` 브랜치에서 작업합니다.
- 작업 완료 후 `develop`을 대상으로 Pull Request를 생성합니다.
- `Frontend Build`와 `Python Test`가 통과한 뒤 병합합니다.
- 기능 브랜치에서 `main`으로 직접 병합하지 않습니다.
- 강제 Push는 사용하지 않습니다.

병합 흐름: `feature/* → develop → main`

## 처음 작업 브랜치를 받는 방법

1. `git fetch origin`
2. `git switch --track origin/feature/담당브랜치`

이미 로컬 브랜치가 있다면:

1. `git switch feature/담당브랜치`
2. `git pull --ff-only origin feature/담당브랜치`

## 작업 전 확인

1. `git branch --show-current`
2. `git status --short`

## 작업 저장

1. `git add 변경한파일`
2. `git diff --cached`
3. `git commit -m "feat: 작업 내용"`
4. `git push`

## Pull Request

- base: `develop`
- compare: 본인의 `feature/*` 브랜치
- 수정 사항이 생기면 같은 브랜치에 추가 커밋 후 Push합니다.
- 새로운 PR을 다시 만들지 않습니다.

## develop 변경사항 반영

1. `git fetch origin`
2. `git switch feature/담당브랜치`
3. `git merge origin/develop`
4. `git push`

## 병합 후 최신화

1. `git switch develop`
2. `git pull --ff-only origin develop`
3. `git fetch --prune`
