# Generation

Hybrid Search와 Reranker가 반환한 LH 공고문 근거를 Qwen에 전달하여
공고문 근거 기반 답변을 생성합니다.

```text
질문
→ Hybrid Search Top 20
→ Reranker Top 5
→ LH 전용 프롬프트
→ llama.cpp Qwen
→ 답변 + 근거
```

## 핵심 정책

- 선택한 LH 공고문 근거만 사용
- 다른 공고나 일반 지식으로 보완 금지
- 금액, 날짜, 주택형, 공급 세대수, 자격 조건 변경 금지
- 표의 행과 열 관계 유지
- 근거 부족 시 확인할 수 없다고 답변
- 답변에 `[근거 N]` 표시

## 실행

1. Qwen GGUF 모델을 llama.cpp `llama-server`로 실행합니다.
2. `run_generation.py`를 VS Code에서 열고 오른쪽 위 실행 버튼을 누릅니다.
3. 공고, 문서 형식, 질문을 차례로 선택·입력합니다.

기본 llama.cpp 주소:

```text
http://127.0.0.1:8080/v1/chat/completions
```

터미널에서도 실행할 수 있습니다.

```bash
python -m rag.generation.run_generation
```

비대화형 실행:

```bash
python -m rag.generation.run_generation   --non-interactive   --announcement announcement_001   --format hwpx   --query "계약금은 얼마야?"
```

## 프롬프트만 확인

```bash
python -m rag.generation.test_prompt_builder
```

## llama.cpp 서버 확인

서버가 실행되지 않으면 다음 오류가 발생합니다.

```text
llama.cpp 서버에 연결할 수 없습니다.
```

`config.py` 또는 실행 인자의 `--llm-base-url`을 실제 서버 주소에 맞게
수정하세요.

## 의존성

추가 외부 Python HTTP 라이브러리는 사용하지 않습니다.
Python 표준 라이브러리 `urllib`로 llama.cpp 서버를 호출합니다.
