# 청킹 및 BGE-M3 임베딩 파이프라인

## 1. 개요

이 모듈은 HWP/HWPX 문서를 구조화한 JSON을 입력으로 받아 다음 작업을 수행합니다.

```text
구조화 JSON
→ 구조 기반 청킹
→ chunks.json
→ BGE-M3 Dense Embedding
→ embeddings.npy + metadata.json + embedding_report.json
```

현재 임베딩 모델은 `BAAI/bge-m3`이며, 각 청크의 `embedding_text`를 1024차원 Dense Vector로 변환합니다.

---

## 2. 주요 특징

- HWP/HWPX 구조화 결과의 섹션 계층 유지
- 문단과 표를 서로 다른 방식으로 청킹
- `content`, `search_text`, `embedding_text` 분리
- 공고별·문서 형식별 결과 분리 저장
- `outputs` 아래 모든 HWP/HWPX 청크 자동 탐색
- BGE-M3 모델을 GPU에 한 번만 로드한 뒤 여러 파일 순차 처리
- 입력 청크 수와 임베딩 벡터 수 1:1 검증
- NaN, Infinity, 0 벡터 검증
- `run_pipeline.py`에서 청킹 및 임베딩 자동 실행 지원

---

## 3. 폴더 구조

```text
one-cycle/
├─ run_pipeline.py
│
├─ chunking/
│  ├─ __init__.py
│  ├─ run_chunking.py
│  ├─ chunker.py
│  ├─ paragraph_chunker.py
│  ├─ table_chunker.py
│  ├─ section_walker.py
│  ├─ text_builder.py
│  ├─ tokenizer.py
│  └─ validator.py
│
├─ embedding/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ models.py
│  ├─ input_loader.py
│  ├─ validator.py
│  ├─ model_loader.py
│  ├─ embedding_generator.py
│  ├─ output_writer.py
│  ├─ run_embeddings.py
│  └─ requirements.txt
│
└─ outputs/
   └─ announcement_*/
      ├─ 03_structured/
      ├─ 04_chunks/
      └─ 05_embeddings/
```

`embedding/__init__.py`는 빈 파일이어도 정상입니다.

---

## 4. Python 가상환경

현재 AWS에서 사용하는 가상환경 경로 예시는 다음과 같습니다.

```bash
source /home/ubuntu/ddokbot/venvs/one-cycle/bin/activate
```

활성화 후 실제 Python 경로를 확인합니다.

```bash
which python
python -c "import sys; print(sys.executable)"
```

두 결과가 다음 경로를 가리켜야 합니다.

```text
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python
```

VS Code Remote SSH를 사용하는 경우에도 Python 인터프리터를 동일한 경로로 선택해야 합니다.

```text
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python
```

---

## 5. 라이브러리 설치

### 5.1 PyTorch

PyTorch는 AWS GPU와 CUDA 환경에 맞게 별도로 설치합니다.

설치 후 확인:

```bash
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

정상 환경에서는 `cuda: True`와 GPU 이름이 출력되어야 합니다.

### 5.2 임베딩 의존성

```bash
python -m pip install -r embedding/requirements.txt
```

`pip install`보다 `python -m pip install`을 권장합니다. 현재 실행 중인 Python 환경에 정확히 설치되기 때문입니다.

FlagEmbedding import 확인:

```bash
python -c "from FlagEmbedding import BGEM3FlagModel; print('FlagEmbedding import 성공')"
```

설치 환경이 꼬인 경우에는 가상환경 Python 경로를 직접 사용합니다.

```bash
/home/ubuntu/ddokbot/venvs/one-cycle/bin/python -m pip install FlagEmbedding
```

---

## 6. 청킹 실행

### 모든 문서 자동 탐색

```bash
python chunking/run_chunking.py
```

또는 전체 파이프라인에서 청킹 단계만 실행:

```bash
python run_pipeline.py --stage chunk
```

청킹 결과:

```text
outputs/announcement_*/04_chunks/hwp/chunks.json
outputs/announcement_*/04_chunks/hwpx/chunks.json
```

---

## 7. 임베딩 실행

### 7.1 전체 HWP/HWPX 자동 탐색

```bash
python -m embedding.run_embeddings --continue-on-error
```

또는 직접 파일 실행:

```bash
python embedding/run_embeddings.py --continue-on-error
```

`run_embeddings.py`는 두 실행 방식을 모두 지원하도록 프로젝트 루트를 `sys.path`에 추가합니다.

### 7.2 파일별 앞 5개 청크 테스트

```bash
python -m embedding.run_embeddings --limit 5 --continue-on-error
```

### 7.3 특정 입력만 실행

```bash
python -m embedding.run_embeddings   --inputs   outputs/announcement_001/04_chunks/hwp/chunks.json   outputs/announcement_001/04_chunks/hwpx/chunks.json
```

---

## 8. run_pipeline.py 연동

`run_pipeline.py`는 하위 프로세스를 실행할 때 `sys.executable`을 사용합니다.

따라서 `run_pipeline.py`를 어떤 Python으로 시작했는지가 중요합니다.

```text
VS Code 또는 터미널
→ 선택된 Python
→ run_pipeline.py
→ sys.executable
→ run_embeddings.py
```

임베딩만 실행:

```bash
python run_pipeline.py --stage embed
```

전체 파이프라인 실행:

```bash
python run_pipeline.py --stage full
```

전체 실행 순서:

```text
Parser
→ HWP/HWPX 비교
→ Normalizer
→ Structure
→ Chunking
→ Embedding
```

현재 `run_pipeline.py`의 임베딩 단계는 대표 형식 하나만 선택하지 않고, 존재하는 모든 HWP/HWPX `chunks.json`을 처리하도록 구성합니다.

---

## 9. 출력 결과

입력:

```text
outputs/announcement_001/04_chunks/hwp/chunks.json
```

출력:

```text
outputs/announcement_001/05_embeddings/hwp/
├─ embeddings.npy
├─ metadata.json
└─ embedding_report.json
```

각 파일의 역할:

### embeddings.npy

청크별 1024차원 Dense Vector 배열입니다.

```text
shape = (청크 수, 1024)
```

### metadata.json

각 벡터와 원본 청크를 연결합니다.

주요 필드:

- `vector_index`
- `chunk_id`
- `document_id`
- `announcement_id`
- `chunk_type`
- `section_path`
- `content`
- `search_text`
- `source`

### embedding_report.json

임베딩 실행 결과와 검증 통계입니다.

주요 항목:

- 모델명
- 장치 및 GPU
- 청크 수
- 벡터 수
- 벡터 차원
- NaN/Infinity/0 벡터 수
- 배치 크기
- 실행 시간

---

## 10. Git에 올리는 파일

다음 파일은 Git에 포함합니다.

```text
chunking/
embedding/
run_pipeline.py
README.md
```

특히 이번 작업에서는 다음 변경사항을 함께 올려야 합니다.

- `embedding/run_embeddings.py`
- `embedding/config.py`
- `embedding/models.py`
- `embedding/input_loader.py`
- `embedding/validator.py`
- `embedding/model_loader.py`
- `embedding/embedding_generator.py`
- `embedding/output_writer.py`
- `embedding/requirements.txt`
- 수정된 `run_pipeline.py`

다음 항목은 Git에 올리지 않습니다.

```text
outputs/
models/
.venv/
venvs/
__pycache__/
*.pyc
.cache/
.env
```

`.gitignore` 예시:

```gitignore
outputs/
models/
.venv/
venvs/
__pycache__/
*.pyc
.cache/
.env
```

---

## 11. Git 업로드 순서

### 11.1 브랜치 확인

```bash
git fetch origin
git switch feature/rag
```

브랜치가 아직 없다면:

```bash
git switch -c feature/rag
```

### 11.2 실행 전 확인

```bash
python -m py_compile   embedding/run_embeddings.py   embedding/model_loader.py   embedding/embedding_generator.py   embedding/output_writer.py   run_pipeline.py
```

임베딩 소량 테스트:

```bash
python -m embedding.run_embeddings --limit 5 --continue-on-error
```

전체 파이프라인의 임베딩 연결 테스트:

```bash
python run_pipeline.py --stage embed
```

### 11.3 변경 파일 확인

```bash
git status
git diff -- run_pipeline.py
git diff -- embedding/
```

`outputs/`가 표시되지 않는지 확인합니다.

### 11.4 스테이징

```bash
git add embedding/
git add chunking/
git add run_pipeline.py
git add README.md
```

청킹 파일이 이미 커밋되어 변경이 없다면 `git add chunking/`은 생략할 수 있습니다.

### 11.5 스테이징 결과 확인

```bash
git status
git diff --cached
```

### 11.6 커밋

```bash
git commit -m "feat: BGE-M3 임베딩 파이프라인 연동"
```

청킹 변경까지 같이 포함한다면:

```bash
git commit -m "feat: 구조 기반 청킹 및 BGE-M3 임베딩 구현"
```

### 11.7 원격 저장소에 push

처음 push하는 브랜치:

```bash
git push -u origin feature/rag
```

이후:

```bash
git push
```

---

## 12. 주의사항

### HWP/HWPX 중복

현재 검증 단계에서는 같은 공고의 HWP와 HWPX 결과를 모두 임베딩합니다.

운영 DB에 적재할 때 동일 내용의 HWP/HWPX를 모두 넣으면 중복 검색 결과가 발생할 수 있으므로, 이후 대표 형식 선택 또는 중복 제거 정책이 필요합니다.

### 모델 파일

BGE-M3 모델은 Hugging Face 캐시에 저장되며 Git에 포함하지 않습니다.

### 출력 파일

`embeddings.npy`와 `metadata.json`은 재생성 가능한 산출물이므로 Git에 포함하지 않습니다.

### 다음 단계

```text
embeddings.npy + metadata.json
→ PostgreSQL + pgvector 적재
→ Vector Search
→ BM25
→ Hybrid Search
→ Reranker
→ Qwen 답변 생성
```
