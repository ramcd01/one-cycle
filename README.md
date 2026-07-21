# Hancom AI Project

HWP/HWPX 문서를 구조적으로 파싱하고, 문서 내 표와 문단 정보를 활용해 RAG 기반 질의응답 서비스를 구현하기 위한 프로젝트입니다.

현재는 실제 LH 공공분양 공고문을 대상으로 HWP/HWPX 문서 구조화 PoC를 진행하고 있습니다.

---

## 1. Project Goal

본 프로젝트의 목표는 HWP/HWPX 문서의 구조를 분석하여 문단, 표, 셀, 병합 정보 등을 유지한 공통 JSON 형태로 변환하고, 이를 기반으로 문서 검색 및 질의응답 서비스를 구현하는 것입니다.

최종 데이터 처리 흐름은 다음과 같습니다.

```text
HWP / HWPX
    ↓
포맷별 Parser
    ↓
공통 구조 JSON
    ↓
Chunk 생성
    ↓
Embedding
    ↓
pgvector
    ↓
RAG 검색
    ↓
LLM 답변
```

---

## 2. Current PoC Status

현재까지 진행된 주요 작업은 다음과 같습니다.

- HWP 문서 파싱 환경 구축
- HWPX 문서 파싱 환경 구축
- HWP/HWPX 공통 JSON 구조 생성
- Table 및 Cell 구조 추출
- `row`, `col`, `row_span`, `col_span` 추출
- Nested Table 재귀 파싱 적용
- 실제 LH 공고문 3종 구조 검증 완료
- HWP/HWPX 구조 비교 완료

현재 다음 단계를 진행할 예정입니다.

```text
공통 JSON Schema v1 확정
        ↓
Text Normalization
        ↓
Chunk 전략 재설계
        ↓
Embedding
        ↓
pgvector 저장
        ↓
RAG 검색 PoC
```

---

## 3. Project Structure

```text
hancom-ai/
│
├─ parser/
│  ├─ hwp_parser.py
│  ├─ hwpx_parser.py
│  ├─ compare_parsers.py
│  ├─ chunker.py
│  ├─ add_section_context.py
│  └─ ...
│
├─ tests/
│  ├─ hwp/
│  └─ hwpx/
│
├─ libs/
│  ├─ hwp/
│  │  └─ hwplib-1.1.8.jar
│  └─ hwpx/
│     └─ hwpxlib-1.0.8.jar
│
├─ test_documents/
│  ├─ announcement_001/
│  ├─ announcement_002/
│  └─ announcement_003/
│
├─ docs/
│
├─ outputs/
│
├─ README.md
├─ requirements.txt
└─ .gitignore
```

### Folder Description

| Folder | Description |
| --- | --- |
| `parser` | HWP/HWPX Parser 및 구조 비교, Chunk 관련 코드 |
| `tests/hwp` | HWP 라이브러리 객체 및 구조 테스트 코드 |
| `tests/hwpx` | HWPX 라이브러리 객체 및 구조 테스트 코드 |
| `libs` | HWP/HWPX Java 라이브러리 |
| `test_documents` | 실제 LH 공고문 테스트 데이터 |
| `docs` | PoC 작업 기록 및 프로젝트 문서 |
| `outputs` | Parser 실행 결과 JSON |

---

## 4. Environment

현재 PoC 환경은 다음과 같습니다.

- Python
- Java
- JPype1
- hwplib 1.1.8
- hwpxlib 1.0.8

Python 패키지는 다음 명령어로 설치합니다.

```bash
pip install -r requirements.txt
```

---

## 5. Virtual Environment

Windows 기준 가상환경을 생성합니다.

```bat
python -m venv venv
```

가상환경을 활성화합니다.

```bat
venv\Scripts\activate
```

필요한 패키지를 설치합니다.

```bat
pip install -r requirements.txt
```

---

## 6. HWP Parser 실행

예시:

```bat
cd C:\Project\hancom-ai\parser

python hwp_parser.py ^
  --hwp_jar_path "C:\Project\hancom-ai\libs\hwp\hwplib-1.1.8.jar" ^
  --file_path "C:\Project\hancom-ai\test_documents\announcement_003\익산평화(공공분양)해약세대입주자모집공고문.hwp" ^
  --output_path "C:\Project\hancom-ai\outputs\output_003_hwp_nested_test.json"
```

정상 실행 시 예시:

```text
================================================================================
HWP 구조 변환 완료
================================================================================
파일: 익산평화(공공분양)해약세대입주자모집공고문.hwp
Section 수: 1
전체 Table 수: 37
출력: C:\Project\hancom-ai\outputs\output_003_hwp_nested_test.json
```

---

## 7. HWPX Parser 실행

예시:

```bat
cd C:\Project\hancom-ai\parser

python hwpx_parser.py ^
  --hwpx_jar_path "C:\Project\hancom-ai\libs\hwpx\hwpxlib-1.0.8.jar" ^
  --file_path "C:\Project\hancom-ai\test_documents\announcement_003\익산평화(공공분양)해약세대입주자모집공고문.hwpx" ^
  --output_path "C:\Project\hancom-ai\outputs\output_003_hwpx_nested_test.json"
```

정상 실행 시 예시:

```text
================================================================================
HWPX 구조 변환 완료
================================================================================
파일: 익산평화(공공분양)해약세대입주자모집공고문.hwpx
Section 수: 1
전체 Table 수: 37
출력: C:\Project\hancom-ai\outputs\output_003_hwpx_nested_test.json
```

---

## 8. Test Documents

현재 실제 LH 공고문 3종을 대상으로 구조 검증을 진행했습니다.

```text
announcement_001
청주지북 B1블록 공공분양주택 잔여세대 추가 입주자모집 공고문

announcement_002
고양창릉 S-4블록 공공분양주택 입주자모집공고문

announcement_003
익산평화 공공분양주택 해약세대 입주자모집공고문
```

테스트용 HWPX 문서는 LH에서 직접 제공된 원본이 아니라, HWP 원본을 한글 프로그램에서 HWPX 형식으로 변환한 파일입니다.

---

## 9. Structure Validation Result

현재까지의 테스트 결과는 다음과 같습니다.

| Document | HWP Table | HWPX Table | Result |
| --- | ---: | ---: | --- |
| announcement_001 | 35 | 35 | Match |
| announcement_002 | 124 | 124 | Match |
| announcement_003 | 37 | 37 | Match |

다음 항목을 기준으로 HWP/HWPX 구조를 비교했습니다.

- Table hierarchy
- Parent Table
- Parent Cell
- `row_count`
- `col_count`
- Cell `row`
- Cell `col`
- `row_span`
- `col_span`

현재 테스트한 3개 문서에서는 HWP/HWPX 간 추출된 Table 구조의 불일치가 확인되지 않았습니다.

---

## 10. Known Issues

### 10.1 HWP/HWPX Text Difference

HWP와 HWPX 간 일부 텍스트 표현 차이가 존재합니다.

예:

```text
HWP
계약금-입주잔금-할부금

HWPX
계약금 - 입주잔금 - 할부금
```

주요 차이는 다음과 같습니다.

- 공백
- 개행
- 특수문자
- 기호 주변 공백

향후 Text Normalization 단계에서 처리할 예정입니다.

### 10.2 Document Order

현재 Paragraph와 Nested Table 구조는 추출할 수 있지만, 복잡한 Cell 내부에서 Paragraph와 Table이 혼합되어 나타나는 경우 실제 문서의 등장 순서를 더 정확하게 보존할 필요가 있습니다.

현재 구조는 개념적으로 다음과 같습니다.

```text
Cell
├─ paragraphs
└─ nested_tables
```

향후에는 필요에 따라 다음과 같이 순서를 유지할 수 있는 구조를 검토합니다.

```text
Cell
└─ blocks
   ├─ Paragraph
   ├─ Table
   └─ Paragraph
```

### 10.3 Complex Table Validation

Nested Table 재귀 파싱은 실제 LH 공고문 3종을 대상으로 1차 검증을 완료했습니다.

다만 향후 다음 항목에 대한 추가 검증이 필요합니다.

- 더 다양한 LH 공고문 구조
- 원문과 구조화 JSON 간 시각적 대조
- 이미지 형태의 표
- 지원하지 않는 문서 구조의 예외 처리
- HWP에서 변환하지 않은 Native HWPX 문서 검증

---

## 11. Next Step

다음 작업은 아래 순서로 진행할 예정입니다.

```text
1. Common JSON Schema v1 확정
2. Text Normalization
3. 원문 순서 보존 방식 검토
4. Chunk 전략 재설계
5. Embedding 적용
6. pgvector 저장
7. Retrieval 테스트
8. RAG 질의응답 PoC
```

---

## 12. Notes

`outputs` 폴더에는 Parser 실행 결과 JSON이 생성됩니다.

Nested Table 재귀 파싱 적용 이전에 생성된 기존 Chunk 및 Enriched Chunk는 최신 Parser 구조를 반영하지 않을 수 있습니다.

따라서 Common JSON Schema v1 확정 후 최신 Parser 결과를 기준으로 다음 데이터를 다시 생성하고 검증할 예정입니다.

```text
chunks_hwp.json
chunks_hwpx.json
chunks_hwp_enriched.json
chunks_hwpx_enriched.json
```

PoC의 상세 작업 과정과 문제 해결 기록은 `docs` 폴더에서 관리합니다.