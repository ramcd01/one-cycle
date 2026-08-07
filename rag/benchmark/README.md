# 모델 일괄 벤치마크

`run_model_benchmark.py`를 VS Code에서 열고 ▶ 실행 버튼을 누르면:

공고 선택 → HWP/HWPX 선택 → 모델/Reranker 1회 로드 → 질문 전체 자동 실행 → TXT/JSON 저장

결과 위치:

```text
outputs/benchmark/
```

같은 공고와 같은 문서 형식을 선택한 뒤 llama-server의 모델만 바꿔 실행하면
Qwen과 Llama 3.1 결과 파일을 따로 얻을 수 있습니다.

질문은 `questions.json`에서 추가·수정할 수 있습니다.
한 질문이 실패해도 다음 질문은 계속 실행됩니다.
