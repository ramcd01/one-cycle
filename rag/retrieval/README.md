# Retrieval

DB 없이 `embeddings.npy`와 `metadata.json`을 이용해 Vector Search + BM25 + RRF 기반 Hybrid Search를 수행합니다.

## 테스트

```bash
python -m rag.retrieval.test_corpus --announcement announcement_001 --format hwpx
```

```bash
python -m rag.retrieval.run_hybrid_search \
  --announcement announcement_001 \
  --format hwpx \
  --query "계약금은 얼마야?"
```

`--format`을 생략하면 HWPX 우선, 없으면 HWP를 사용합니다.
