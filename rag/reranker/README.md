# Reranker

Hybrid Search가 반환한 후보를 질문과 직접 비교하여 최종 순서를 다시 정렬합니다.

```text
사용자 질문
→ Hybrid Search Top 20
→ BGE Reranker
→ 최종 Top 5
→ LLM
```

## 사용 모델

```text
BAAI/bge-reranker-v2-m3
```

## 폴더 구성

```text
rag/reranker/
├─ __init__.py
├─ config.py
├─ models.py
├─ model_loader.py
├─ reranker.py
├─ run_reranker.py
├─ test_reranker_model.py
└─ README.md
```

## 실행 방법

VS Code에서 `run_reranker.py`를 열고 오른쪽 위 실행 버튼을 누르면 됩니다.

실행 흐름:

```text
공고 선택
→ HWP/HWPX 선택
→ 질문 입력
→ Hybrid Search 실행
→ Reranker 실행
→ 최종 Top 5 출력
```

터미널 실행도 지원합니다.

```bash
python -m rag.reranker.run_reranker
```

특정 값으로 비대화형 실행:

```bash
python -m rag.reranker.run_reranker   --non-interactive   --announcement announcement_001   --format hwpx   --query "계약금은 얼마야?"
```

## 모델 테스트

```bash
python -m rag.reranker.test_reranker_model
```

## 주요 설정

`config.py`

```text
hybrid_candidate_top_k = 20
rerank_top_k = 5
batch_size = 4
max_length = 1024
normalize_scores = True
text_field = content
```

GPU 메모리 부족 시 `batch_size`를 2 또는 1로 줄입니다.

## 의존성

기존 임베딩 환경의 `FlagEmbedding`, `torch`, `numpy`를 그대로 사용합니다.

```bash
python -m pip install FlagEmbedding numpy
```
