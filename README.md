# DDOK

> HWP/HWPX 공공문서 기반 AI 정보 탐색 및 질의응답 서비스

DDOK는 복잡한 HWP/HWPX 공공문서를 구조적으로 분석하고, 문서 안의 본문·표·병합 셀·중첩 표 정보를 최대한 유지하여 향후 RAG 기반 질의응답에 활용하기 위한 프로젝트입니다.

현재는 LH 공공분양 입주자모집공고문을 대상으로 HWP/HWPX 문서 파싱 및 구조화 PoC를 진행하고 있습니다.

---

# 1. 프로젝트 목적

LH 입주자모집공고문과 같은 공공문서는 분량이 길고, 사용자가 실제로 필요로 하는 정보가 문서 여러 위치에 흩어져 있습니다.

예를 들어 사용자가 자주 확인해야 하는 정보는 다음과 같습니다.

- 신청 일정
- 신청 자격
- 소득 기준
- 자산 기준
- 공급 대상
- 공급 가격
- 제출 서류
- 당첨자 발표 일정

하지만 이러한 정보는 단순한 본문 텍스트뿐만 아니라 표, 병합 셀, 중첩 표 등 복잡한 구조 안에도 포함되어 있습니다.

따라서 단순히 문서의 텍스트만 추출하면 정보 간 관계가 손실될 수 있습니다.

예를 들어 원본 문서가 다음과 같은 표 구조를 가지고 있다고 가정합니다.

```text
구분      | 소득 기준    | 자산 기준
신혼부부  | 130% 이하    | 3억 이하
생애최초  | 130% 이하    | 3억 이하
```

이를 단순 텍스트로만 추출하면 다음과 같이 변할 수 있습니다.

```text
구분
소득 기준
자산 기준
신혼부부
130% 이하
3억 이하
생애최초
130% 이하
3억 이하
```

이 경우 `130% 이하`가 어떤 공급 유형의 조건인지, `3억 이하`가 어떤 행에 속하는지 구조적 관계를 잃을 수 있습니다.

RAG 기반 질의응답에서 이러한 구조 손실은 잘못된 검색 결과나 잘못된 답변으로 이어질 수 있습니다.

따라서 본 프로젝트에서는 문서를 단순 텍스트로 변환하는 것이 아니라 다음과 같은 구조를 최대한 유지하는 것을 목표로 합니다.

```text
Document
└─ Section
   └─ Block
      ├─ Paragraph
      └─ Table
         └─ Cell
            ├─ row
            ├─ col
            ├─ row_span
            ├─ col_span
            ├─ text
            └─ nested_table
```

---

# 2. 현재 PoC의 목적

현재 단계의 목적은 RAG를 바로 구현하는 것이 아닙니다.

먼저 HWP와 HWPX 문서를 안정적으로 구조화할 수 있는지를 확인하는 단계입니다.

현재 PoC에서는 다음 항목을 검증합니다.

```text
1. HWP 문서에서 본문과 표를 추출할 수 있는가?
2. HWPX 문서에서도 동일한 정보를 추출할 수 있는가?
3. 표의 행과 열 정보를 유지할 수 있는가?
4. 병합 셀 정보를 유지할 수 있는가?
5. 표 안의 중첩 표(Nested Table)를 추출할 수 있는가?
6. 동일 문서의 HWP/HWPX 결과가 구조적으로 동일한가?
7. Paragraph 개수와 순서가 유지되는가?
8. 텍스트 차이가 발생한다면 어떤 유형의 차이인가?
```

이 검증이 완료되어야 이후 다음 단계로 넘어갈 수 있습니다.

```text
Common JSON Schema 확정
→ Chunking
→ Embedding
→ Vector DB 저장
→ Retrieval
→ RAG 질의응답
```

---

# 3. 왜 HWP와 HWPX를 각각 파싱하는가?

HWP와 HWPX는 같은 한글 문서 계열이지만 내부 저장 방식이 서로 다릅니다.

```text
HWP
→ 바이너리 기반 문서 형식

HWPX
→ XML 기반 문서 형식
```

따라서 두 형식을 같은 방식으로 처리할 수 없습니다.

현재 PoC에서는 각각 다른 Parser를 사용하여 문서를 읽은 뒤 최종적으로 동일한 형태의 JSON 구조로 변환하는 것을 목표로 합니다.

```text
HWP
 ↓
hwp_parser.py
 ↓
Common JSON


HWPX
 ↓
hwpx_parser.py
 ↓
Common JSON
```

최종적으로 HWP와 HWPX가 동일한 Common JSON 구조로 변환되어야 이후 RAG 단계에서 동일한 Chunking 및 검색 로직을 사용할 수 있습니다.

---

# 4. 전체 처리 흐름

현재 파싱 PoC의 전체 흐름은 다음과 같습니다.

```text
                HWP 원본
                   │
                   ▼
            hwp_parser.py
                   │
                   ▼
        announcement_XXX_hwp.json
                   │
                   │
                   ├───────────────┐
                   │               │
                   ▼               ▼
              구조 비교      compare_parsers.py
                   ▲               ▲
                   │               │
                   ├───────────────┘
                   │
        announcement_XXX_hwpx.json
                   ▲
                   │
            hwpx_parser.py
                   ▲
                   │
               HWPX 문서
```

기본 실행 순서는 다음과 같습니다.

```text
1. HWP 파싱
2. HWPX 파싱
3. 두 JSON 비교
4. 구조 차이 확인
5. Paragraph 차이 확인
6. 텍스트 차이 확인
```

이 과정을 편하게 실행할 수 있도록 프로젝트 루트에 `run_parser.py`를 제공합니다.

---

# 5. 프로젝트 구조

현재 파싱 PoC 기준 프로젝트 구조는 다음과 같습니다.

```text
hancom-ai/
│
├─ run_parser.py
│
├─ parser/
│  ├─ hwp_parser.py
│  ├─ hwpx_parser.py
│  └─ compare_parsers.py
│
├─ libs/
│  ├─ hwp/
│  │  └─ hwplib-1.1.8.jar
│  │
│  └─ hwpx/
│     └─ hwpxlib-1.0.8.jar
│
├─ test_documents/
│  ├─ announcement_001/
│  │  ├─ *.hwp
│  │  ├─ *.hwpx
│  │  └─ *.pdf
│  │
│  ├─ announcement_002/
│  │  ├─ *.hwp
│  │  ├─ *.hwpx
│  │  └─ *.pdf
│  │
│  └─ announcement_003/
│     ├─ *.hwp
│     ├─ *.hwpx
│     └─ *.pdf
│
├─ outputs/
│  ├─ announcement_001_hwp.json
│  ├─ announcement_001_hwpx.json
│  ├─ announcement_002_hwp.json
│  ├─ announcement_002_hwpx.json
│  ├─ announcement_003_hwp.json
│  └─ announcement_003_hwpx.json
│
├─ archive/
│  ├─ chunk/
│  ├─ debug/
│  └─ tests/
│
├─ README.md
├─ requirements.txt
└─ .gitignore
```

---

# 6. 각 폴더와 파일의 역할

## `run_parser.py`

팀원이 가장 먼저 실행하는 통합 실행 파일입니다.

기존에는 HWP Parser, HWPX Parser, 비교 스크립트를 각각 긴 명령어로 실행해야 했지만, `run_parser.py`를 사용하면 메뉴에서 문서와 작업만 선택하면 됩니다.

즉 팀원 입장에서는 다음 명령어 하나만 기억하면 됩니다.

```bash
python run_parser.py
```

---

## `parser/`

현재 실제 파싱 PoC에서 사용하는 핵심 코드가 들어 있습니다.

```text
parser/
├─ hwp_parser.py
├─ hwpx_parser.py
└─ compare_parsers.py
```

### `hwp_parser.py`

HWP 문서를 읽어 구조화 JSON으로 변환합니다.

### `hwpx_parser.py`

HWPX 문서를 읽어 구조화 JSON으로 변환합니다.

### `compare_parsers.py`

동일한 문서의 HWP/HWPX 파싱 결과를 비교합니다.

---

## `libs/`

Parser 실행에 필요한 Java 라이브러리가 들어 있습니다.

```text
libs/
├─ hwp/
│  └─ hwplib-1.1.8.jar
│
└─ hwpx/
   └─ hwpxlib-1.0.8.jar
```

---

## `test_documents/`

실제 파싱 테스트에 사용하는 LH 공고문을 저장합니다.

각 공고별로 다음 형식을 함께 관리합니다.

```text
HWP
HWPX
PDF
```

현재 HWPX 테스트 파일은 HWP 원본을 HWPX로 변환하여 사용한 파일입니다.

PDF는 향후 Parser 결과와 원문을 시각적으로 대조할 때 사용합니다.

---

## `outputs/`

Parser 실행 결과 생성된 JSON 파일을 저장합니다.

예:

```text
announcement_001_hwp.json
announcement_001_hwpx.json
```

---

## `archive/`

현재 실행 흐름에서는 사용하지 않지만 PoC 과정에서 작성했던 실험용 코드를 보관합니다.

```text
archive/
├─ chunk/
├─ debug/
└─ tests/
```

### `archive/chunk`

초기 Chunking 실험 코드

### `archive/debug`

Parser 내부 구조 확인을 위해 사용한 디버그 코드

### `archive/tests`

`hwplib`, `hwpxlib`의 객체 및 메서드 구조를 탐색하기 위해 사용한 초기 테스트 코드

현재 팀원이 파싱 PoC를 이해할 때는 `archive` 폴더를 확인하지 않아도 됩니다.

---

# 7. 환경 설정

현재 PoC 실행에는 다음 환경이 필요합니다.

```text
Python
Java
JPype1
hwplib 1.1.8
hwpxlib 1.0.8
```

Python 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

가상환경을 사용하는 경우 예시는 다음과 같습니다.

```bat
python -m venv prj
```

가상환경 활성화:

```bat
prj\Scripts\activate
```

프로젝트 루트로 이동합니다.

```bat
cd C:\Project\hancom-ai
```

---

# 8. Quick Start

가상환경을 활성화한 후 프로젝트 루트에서 다음 명령어를 실행합니다.

```bash
python run_parser.py
```

실행하면 먼저 테스트할 문서를 선택합니다.

```text
========================================
DDOK Parser Test
========================================

테스트할 문서를 선택하세요.

1. announcement_001
2. announcement_002
3. announcement_003
0. 종료

선택:
```

문서를 선택하면 실행할 작업을 선택합니다.

```text
실행할 작업을 선택하세요.

1. HWP 파싱
2. HWPX 파싱
3. HWP + HWPX 모두 파싱
4. HWP/HWPX 결과 비교
5. 전체 실행 (HWP → HWPX → 비교)
0. 이전 메뉴

선택:
```

일반적인 전체 파싱 검증에서는 `5번`을 선택합니다.

```text
HWP 파싱
→ HWP JSON 생성
→ HWPX 파싱
→ HWPX JSON 생성
→ HWP/HWPX 결과 비교
```

---

# 9. 왜 `run_parser.py`를 사용하는가?

기존에는 Parser를 실행할 때 다음과 같이 여러 경로를 직접 입력해야 했습니다.

```text
Parser 경로
JAR 경로
HWP/HWPX 파일 경로
Output 경로
```

이 방식은 다음 문제가 있습니다.

- 명령어가 길다.
- 경로 입력 실수가 발생하기 쉽다.
- 팀원이 각 Parser의 인자를 외워야 한다.
- 어떤 순서로 실행해야 하는지 별도로 알아야 한다.
- 비교 작업을 누락할 수 있다.

`run_parser.py`는 이러한 과정을 하나의 실행 흐름으로 통합합니다.

```text
사용자
 ↓
python run_parser.py
 ↓
문서 선택
 ↓
작업 선택
 ↓
Parser 자동 실행
 ↓
JSON 생성
 ↓
비교 실행
```

실제 파싱 로직은 기존처럼 각각 분리된 상태로 유지합니다.

```text
run_parser.py
   │
   ├─ hwp_parser.py
   ├─ hwpx_parser.py
   └─ compare_parsers.py
```

즉 `run_parser.py`는 Parser 로직을 대체하는 파일이 아니라 실행을 편하게 해주는 진입점입니다.

---

# 10. `hwp_parser.py`

## 역할

HWP 문서를 읽어 구조화 JSON으로 변환합니다.

HWP는 바이너리 기반 문서 형식이므로 현재 PoC에서는 Java 기반 `hwplib` 라이브러리를 JPype를 통해 Python에서 호출합니다.

사용 라이브러리:

```text
hwplib-1.1.8.jar
```

처리 흐름:

```text
HWP
 ↓
hwplib
 ↓
Section
 ↓
Paragraph
 ↓
Control
 ↓
Table
 ↓
Cell
 ↓
JSON
```

주요 추출 대상:

- Section
- Paragraph
- Table
- Cell
- row
- col
- row_span
- col_span
- Cell Text
- Nested Table

## 왜 실행하는가?

HWP 원본 문서의 구조를 JSON으로 변환하여 HWPX 파싱 결과와 비교하기 위해 실행합니다.

최종적으로는 HWP와 HWPX를 동일한 Common JSON 구조로 변환하는 것이 목적입니다.

---

# 11. `hwpx_parser.py`

## 역할

HWPX 문서를 읽어 구조화 JSON으로 변환합니다.

현재 PoC에서는 Java 기반 `hwpxlib`을 JPype를 통해 호출합니다.

사용 라이브러리:

```text
hwpxlib-1.0.8.jar
```

처리 흐름:

```text
HWPX
 ↓
hwpxlib
 ↓
Section
 ↓
Paragraph
 ↓
Run
 ↓
RunItem
 ↓
Table
 ↓
Cell
 ↓
JSON
```

## 왜 실행하는가?

HWP와 HWPX는 내부 저장 방식이 서로 다르기 때문에 각각 별도의 Parser가 필요합니다.

하지만 최종 RAG 단계에서는 파일 형식과 관계없이 동일한 JSON 구조가 필요합니다.

따라서 HWPX도 별도로 파싱한 뒤 HWP 결과와 구조적으로 비교합니다.

---

# 12. `compare_parsers.py`

## 역할

동일한 문서를 HWP와 HWPX로 각각 파싱한 결과를 비교합니다.

입력:

```text
HWP Parser 결과 JSON
HWPX Parser 결과 JSON
```

비교 대상:

```text
Table 구조
Table 크기
Cell 위치
Row Span
Column Span
Cell Text
Paragraph 개수
Paragraph 순서
Paragraph Text
```

## 왜 실행하는가?

두 Parser가 모두 정상적으로 실행되었다고 해서 동일한 구조를 추출했다고 판단할 수는 없습니다.

예를 들어 다음 결과가 나올 수 있습니다.

```text
HWP Table 수  : 35
HWPX Table 수 : 35
```

Table 개수는 같지만 서로 다른 Table을 추출했을 가능성도 있습니다.

따라서 실제 Cell 구조를 비교해야 합니다.

```text
Table
├─ row_count
├─ col_count
└─ Cell
   ├─ row
   ├─ col
   ├─ row_span
   └─ col_span
```

이 과정을 통해 HWP와 HWPX가 동일한 Common JSON 구조로 변환될 수 있는지를 검증합니다.

---

# 13. Parser 개별 실행 방법

일반적인 테스트에서는 `run_parser.py` 사용을 권장합니다.

다만 Parser를 개별적으로 실행해야 할 경우 다음과 같이 실행할 수 있습니다.

## HWP Parser

```bat
cd C:\Project\hancom-ai\parser

python hwp_parser.py ^
  --hwp_jar_path "C:\Project\hancom-ai\libs\hwp\hwplib-1.1.8.jar" ^
  --file_path "HWP 파일 경로" ^
  --output_path "출력 JSON 경로"
```

---

## HWPX Parser

```bat
python hwpx_parser.py ^
  --hwpx_jar_path "C:\Project\hancom-ai\libs\hwpx\hwpxlib-1.0.8.jar" ^
  --file_path "HWPX 파일 경로" ^
  --output_path "출력 JSON 경로"
```

---

## HWP/HWPX 결과 비교

```bat
python compare_parsers.py ^
  --hwp "C:\Project\hancom-ai\outputs\announcement_003_hwp.json" ^
  --hwpx "C:\Project\hancom-ai\outputs\announcement_003_hwpx.json"
```

---

# 14. 비교 결과 해석

비교 결과에서는 크게 두 종류의 차이를 확인합니다.

```text
구조 차이
텍스트 차이
```

---

## 구조 차이

다음 항목이 다르면 구조 차이로 판단합니다.

```text
Table 크기
Cell 위치
Row Span
Column Span
Nested Table 구조
```

구조 차이는 향후 RAG 검색 정확도에 직접적인 영향을 줄 수 있기 때문에 중요하게 확인합니다.

---

## 텍스트 차이

현재 테스트에서 발견된 텍스트 차이는 대부분 공백 차이입니다.

예:

```text
HWP
■현장 접수

HWPX
■ 현장 접수
```

또는:

```text
HWP
확인후

HWPX
확인 후
```

또는:

```text
HWP
계약금-입주잔금-할부금

HWPX
계약금 - 입주잔금 - 할부금
```

이러한 차이는 정보 손실이라기보다 문서 변환 또는 Parser 처리 과정에서 발생한 공백 차이에 가깝습니다.

따라서 향후 Text Normalization 단계에서 별도로 처리할 수 있습니다.

---

# 15. 현재 테스트 결과

현재 LH 공고문 3종을 사용하여 테스트했습니다.

| 문서 | HWP 전체 Table | HWPX 전체 Table |
| --- | ---: | ---: |
| announcement_001 | 35 | 35 |
| announcement_002 | 124 | 124 |
| announcement_003 | 37 | 37 |

현재 Parser 기준으로 HWP와 HWPX에서 추출된 전체 Table 개수는 동일합니다.

또한 현재 `compare_parsers.py`로 비교된 범위에서는 Cell 구조가 동일하게 확인되고 있습니다.

텍스트 차이는 주로 공백 관련 차이였습니다.

```text
■신청자격
■ 신청자격
```

```text
확인후
확인 후
```

```text
계약금-입주잔금
계약금 - 입주잔금
```

---

# 16. 현재 확인된 한계

현재 PoC가 완전히 종료된 것은 아닙니다.

아래 항목에 대한 추가 검증이 필요합니다.

---

## 16.1 Nested Table 전체 재귀 비교

Parser 실행 결과에서는 다음과 같은 전체 Table 수가 확인되었습니다.

```text
announcement_001 : 35
announcement_002 : 124
announcement_003 : 37
```

하지만 현재 `compare_parsers.py` 비교 출력에서는 일부 최상위 Table을 중심으로 비교하고 있습니다.

예를 들어 `announcement_003`의 Parser 결과는 37개 Table이지만 비교 결과에서는 11개의 최상위 Table이 출력되었습니다.

따라서 향후 `compare_parsers.py`가 Nested Table까지 재귀적으로 탐색하여 전체 Table 구조를 비교하도록 보완해야 합니다.

---

## 16.2 Cell 내부 원문 순서 보존

Cell 내부에는 다음과 같은 구조가 존재할 수 있습니다.

```text
Paragraph
Table
Paragraph
```

현재 Paragraph와 Nested Table을 각각 별도 필드로 저장할 경우 원본 순서가 손실될 가능성이 있습니다.

따라서 향후 다음과 같은 구조를 검토합니다.

```text
Cell
└─ blocks
   ├─ Paragraph
   ├─ Table
   └─ Paragraph
```

이 구조를 사용하면 Cell 내부의 실제 문서 순서를 유지할 수 있습니다.

---

## 16.3 HWPX 원본 검증

현재 테스트에 사용한 HWPX는 LH에서 직접 제공한 Native HWPX가 아니라 HWP 원본을 HWPX로 변환한 파일입니다.

따라서 HWP와 HWPX Parser 결과가 동일하더라도 변환 과정의 영향을 완전히 배제할 수 없습니다.

향후 Native HWPX 문서에 대한 추가 테스트가 필요합니다.

---

## 16.4 Parser 간 일치만으로는 완전성을 증명할 수 없음

HWP Parser와 HWPX Parser 결과가 동일하더라도 두 Parser가 동일한 요소를 함께 누락했을 가능성이 있습니다.

따라서 최종 검증에서는 PDF 또는 실제 한글 원문과 직접 대조해야 합니다.

검증 대상:

```text
Paragraph
Table
Nested Table
병합 셀
Cell 내부 순서
문서 전체 순서
```

---

# 17. 현재 개발 단계

현재 진행 단계는 다음과 같습니다.

```text
[진행 중]
HWP/HWPX Parser 검증
        ↓
Nested Table 전체 비교
        ↓
Cell 내부 순서 검증
        ↓
원문 대조
        ↓
Common JSON Schema v1 확정
```

아직 Chunking 단계로 넘어가기 전입니다.

기존 Chunk 관련 코드는 현재 Parser 구조 확정 이전에 작성된 코드이므로 `archive/chunk`에 보관합니다.

Common JSON Schema v1이 확정된 이후 Chunking 코드를 다시 설계할 예정입니다.

---

# 18. 다음 단계

현재 파싱 PoC 이후 작업 순서는 다음과 같습니다.

```text
1. compare_parsers.py Nested Table 재귀 비교 보완
2. HWP/HWPX 전체 구조 재비교
3. Cell 내부 Paragraph/Table 원문 순서 확인
4. PDF 및 원문과 Parser 결과 대조
5. Common JSON Schema v1 확정
6. Text Normalization
7. Chunk 설계
8. Embedding
9. pgvector 저장
10. Retrieval 테스트
11. RAG 질의응답 PoC
```

---

# 19. 핵심 요약

현재 파싱 PoC에서 팀원이 기본적으로 사용하는 명령어는 하나입니다.

```bash
python run_parser.py
```

실행 후 다음 흐름으로 테스트합니다.

```text
테스트 문서 선택
 ↓
전체 실행 선택
 ↓
HWP Parser
 ↓
HWP JSON
 ↓
HWPX Parser
 ↓
HWPX JSON
 ↓
HWP/HWPX 비교
```

실제 핵심 Parser 파일은 다음 3개입니다.

```text
hwp_parser.py
→ HWP 문서를 구조화 JSON으로 변환

hwpx_parser.py
→ HWPX 문서를 구조화 JSON으로 변환

compare_parsers.py
→ HWP/HWPX 파싱 결과의 구조와 텍스트를 비교
```

`run_parser.py`는 위 3개의 코드를 편하게 실행하기 위한 통합 진입점입니다.

현재 단계에서 가장 중요한 목표는 단순히 Parser가 실행되는 것이 아닙니다.

> HWP와 HWPX라는 서로 다른 문서 형식에서 동일한 의미와 구조를 안정적으로 추출하고, 이를 하나의 Common JSON 구조로 통합할 수 있는지 검증하는 것이 핵심입니다.

이 구조가 검증되어야 이후 Chunking과 RAG 검색 단계에서 신뢰할 수 있는 문서 데이터를 사용할 수 있습니다.