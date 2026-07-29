# DDOK

> HWP/HWPX 공공문서 기반 AI 정보 탐색 및 질의응답 서비스

DDOK는 복잡한 공공문서를 구조적으로 분석하고, 문서 안의 본문·표·병합 셀·중첩 표 정보를 최대한 보존하여 검색과 RAG 기반 질의응답에 활용하기 위한 프로젝트입니다.

현재는 **LH 입주자모집공고문 HWP/HWPX 문서**를 대상으로 다음 문서 처리 Pipeline을 구현하고 있습니다.

```text
HWP / HWPX
    ↓
Parsing
    ↓
Normalization
    ↓
Structure
    ↓
Chunking
    ↓
Embedding
    ↓
Vector DB / Retrieval / RAG  [다음 단계]
```

---

## 1. 프로젝트 목적

LH 입주자모집공고문은 분량이 길고, 사용자가 실제로 확인해야 하는 정보가 문서 여러 위치에 흩어져 있습니다.

대표적으로 다음과 같은 정보가 본문과 표에 나뉘어 포함됩니다.

- 신청 일정
- 신청 자격
- 소득 및 자산 기준
- 공급 대상과 공급 규모
- 공급 가격 및 납부 조건
- 제출 서류
- 당첨자 발표 일정
- 계약 및 입주 관련 유의사항

이러한 문서를 단순 텍스트로만 변환하면 행과 열의 관계, 병합 셀, 중첩 표, 제목과 본문 사이의 구조가 손실될 수 있습니다.

예를 들어 원문이 다음과 같은 표라면:

```text
구분      | 소득 기준 | 자산 기준
신혼부부  | 130% 이하 | 3억 이하
생애최초  | 130% 이하 | 3억 이하
```

단순 텍스트 추출 결과는 다음처럼 관계가 불명확해질 수 있습니다.

```text
구분
소득 기준
자산 기준
신혼부부
130% 이하
3억 이하
```

DDOK는 문서를 단순 문자열이 아니라 다음과 같은 구조로 변환하는 것을 목표로 합니다.

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

## 2. 현재 구현 범위

현재 저장소에서는 다음 단계가 연결되어 있습니다.

| 단계 | 상태 | 설명 |
| --- | --- | --- |
| HWP Parsing | 구현 | Java `hwplib`을 JPype로 호출하여 본문과 표 추출 |
| HWPX Parsing | 구현 | Java `hwpxlib`을 JPype로 호출하여 본문과 표 추출 |
| HWP/HWPX 비교 | 구현 | 동일 문서의 구조와 텍스트 차이 비교 |
| Normalization | 구현 | 형식별 Parser 결과를 공통 구조로 정규화 |
| Structure Step 1~3 | 구현 | 제목·계층·도메인·표 구조화 처리 |
| Chunking | 구현 | 문단과 표 구조를 검색 단위 Chunk로 변환 |
| Embedding | 구현 | Qwen3 Embedding 모델로 벡터 생성 |
| Vector DB 저장 | 미구현 | PostgreSQL + pgvector 연결 예정 |
| Retrieval | 미구현 | 질문과 관련된 Chunk 검색 예정 |
| RAG 질의응답 | 미구현 | 검색 근거 기반 답변 생성 예정 |
| API·UI 연결 | 미구현 | FastAPI 및 사용자 화면과 연결 예정 |

현재는 문서 처리 Pipeline의 연결을 완료하고, **구조화 품질을 개선하는 단계**입니다.

세부 구현 상태와 확인된 문제는 [`docs/PIPELINE_STATUS.md`](docs/PIPELINE_STATUS.md)에서 확인할 수 있습니다.

---

## 3. HWP와 HWPX를 각각 처리하는 이유

HWP와 HWPX는 같은 한글 문서 계열이지만 내부 저장 방식이 다릅니다.

```text
HWP  → 바이너리 기반 문서 형식
HWPX → XML 기반 문서 형식
```

따라서 형식별 Parser를 각각 실행한 후 공통 JSON 구조로 정규화합니다.

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

HWP와 HWPX가 동일한 공통 구조로 변환되어야 이후 Chunking, Embedding, 검색 로직을 문서 형식과 관계없이 공통으로 사용할 수 있습니다.

---

## 4. 전체 처리 흐름

```text
test_documents/<document_id>/
        │
        ├─ *.hwp
        └─ *.hwpx
        │
        ▼
01_parsed
        │
        ▼
02_normalized
        │
        ▼
03_structured
        │
        ▼
04_chunks
        │
        ▼
05_embeddings
```

문서 폴더에 HWP만 있으면 HWP만 처리하고, HWPX만 있으면 HWPX만 처리합니다. 두 형식이 모두 있으면 형식별로 처리한 뒤 비교할 수 있습니다.

Embedding 단계에서는 동일 공고의 HWP와 HWPX를 모두 중복 처리하지 않고, **공고별 대표 Chunk 결과 하나**를 선택합니다.

---

## 5. 프로젝트 구조

```text
one-cycle/
├─ run_pipeline.py
│
├─ config/
│  ├─ __init__.py
│  └─ paths.py
│
├─ parser/
│  ├─ hwp_parser.py
│  ├─ hwpx_parser.py
│  └─ compare_parsers.py
│
├─ normalizer/
│  └─ document_normalizer.py
│
├─ structure/
│  ├─ run_structure.py
│  ├─ build_document_step1.py
│  ├─ buid_domain_step2.py
│  └─ build_table_step3.py
│
├─ chunking/
│  ├─ run_chunking.py
│  └─ build_chunks.py
│
├─ embedding/
│  └─ run_embeddings.py
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
│  ├─ announcement_003/
│  └─ announcement_004/
│
├─ docs/
│  └─ PIPELINE_STATUS.md
│
├─ requirements.txt
├─ README.md
└─ .gitignore
```

`outputs/` 폴더는 Pipeline 실행 시 자동 생성되며 GitHub에는 업로드하지 않습니다.

---

## 6. 실행 환경

권장 환경:

```text
Python 3.12
Java 17
Windows 10/11
```

Parser 실행에는 다음 Java 라이브러리를 사용합니다.

```text
libs/hwp/hwplib-1.1.8.jar
libs/hwpx/hwpxlib-1.0.8.jar
```

Embedding 단계에서는 다음 Python 라이브러리가 추가로 필요합니다.

```text
torch
sentence-transformers
```

---

## 7. 설치 방법

### 7.1 저장소 복제

```bash
git clone https://github.com/ramcd01/one-cycle.git
cd one-cycle
git switch parsing_test
```

### 7.2 가상환경 생성 및 활성화

Windows CMD 기준:

```bat
python -m venv prj
prj\Scripts\activate
```

### 7.3 Python 패키지 설치

```bash
pip install -r requirements.txt
pip install torch sentence-transformers
```

현재 `requirements.txt`에는 Parser와 기존 프로젝트 패키지가 포함되어 있으며, Embedding 실행에 필요한 `torch`, `sentence-transformers`는 별도로 설치합니다.

### 7.4 Java 확인

```bash
java -version
```

Java가 인식되지 않으면 Java 17을 설치한 뒤 `JAVA_HOME`과 `PATH`를 설정해야 합니다.

---

## 8. Quick Start

프로젝트 루트에서 다음 명령을 실행합니다.

```bash
python run_pipeline.py
```

실행 메뉴:

```text
1. 테스트 문서 현황 확인
2. HWP 전체 파싱
3. HWPX 전체 파싱
4. 분석 가능한 문서 전체 파싱
5. HWP/HWPX 비교 가능한 문서 비교
6. Parser JSON 전체 정규화
7. 정규화 JSON 전체 구조화
8. 최종 구조화 JSON 전체 청킹
9. 공고별 대표 Chunk JSON 임베딩
10. 전체 Pipeline 실행
0. 종료
```

처음 실행할 때는 `1번`으로 테스트 문서 인식 상태를 확인하는 것을 권장합니다.

전체 단계를 한 번에 실행하려면 `10번`을 선택합니다.

CPU 환경에서는 Embedding에 시간이 오래 걸릴 수 있으므로 단계별 검증이 필요할 때는 `2번`부터 `9번`까지 순서대로 실행하는 것이 안전합니다.

---

## 9. 출력 구조

결과는 문서별·단계별로 저장됩니다.

```text
outputs/<document_id>/
├─ 01_parsed/
│  ├─ hwp.json
│  └─ hwpx.json
│
├─ 02_normalized/
│  ├─ hwp.json
│  └─ hwpx.json
│
├─ 03_structured/
│  ├─ hwp/
│  │  ├─ step1-1_items.json
│  │  ├─ step1-2_heading_scheme.json
│  │  ├─ step1-3_hierarchy.json
│  │  ├─ step2-1_normalized_titles.json
│  │  ├─ step2-2_domain_matches.json
│  │  ├─ step2-3_domain_tagged.json
│  │  ├─ step2-4_hierarchy_conflicts.json
│  │  ├─ step2-5_domain_repaired.json
│  │  ├─ step3-1_table_headers.json
│  │  ├─ step3-2_table_mappings.json
│  │  └─ step3-3_structured_tables.json
│  └─ hwpx/
│     └─ 동일한 구조화 중간 산출물
│
├─ 04_chunks/
│  ├─ hwp/
│  │  └─ chunks.json
│  └─ hwpx/
│     └─ chunks.json
│
└─ 05_embeddings/
   ├─ hwp/
   │  ├─ embeddings.npy
   │  └─ metadata.json
   └─ hwpx/
      ├─ embeddings.npy
      └─ metadata.json
```

입력 문서에 존재하지 않는 형식의 결과 파일은 생성되지 않습니다.

---

## 10. 단계별 설명

### 10.1 Parsing

HWP와 HWPX를 각각 읽어 문단, 표, 셀, 병합 정보와 중첩 표를 JSON으로 추출합니다.

주요 대상:

```text
Section
Paragraph
Table
Cell
row / col
row_span / col_span
Cell Text
Nested Table
```

### 10.2 Parser 결과 비교

동일 문서의 HWP/HWPX 결과를 비교합니다.

비교 대상:

```text
Table 구조와 크기
Cell 위치
Row Span / Column Span
Cell Text
Paragraph 개수와 순서
Paragraph Text
```

### 10.3 Normalization

형식별 Parser 결과를 후속 단계에서 공통으로 사용할 수 있도록 정규화합니다.

### 10.4 Structure

다음 세 단계로 문서 구조를 분석합니다.

```text
Step 1 → 제목 후보 탐지 및 Section 계층 구성
Step 2 → 제목 정규화, 도메인 분류 및 계층 보정
Step 3 → 표 Header 분석과 구조화
```

### 10.5 Chunking

구조화 결과를 검색과 Embedding에 사용할 Chunk 단위로 변환합니다.

현재 지원하는 주요 Chunk 유형:

```text
paragraph
row_records
key_value
table_fallback
```

표 구조화 결과를 사용할 수 없는 경우 원문 손실을 막기 위해 `table_fallback`으로 처리합니다.

### 10.6 Embedding

현재 사용하는 모델:

```text
Qwen/Qwen3-Embedding-0.6B
```

기본 설정:

```text
vector dimension : 1024
normalized       : true
batch size       : 4
device           : CUDA 사용 가능 시 cuda, 아니면 cpu
```

결과 파일:

```text
embeddings.npy
metadata.json
```

기존 결과가 현재 Chunk와 일치하면 재사용하고, 변경된 Chunk는 다시 Embedding합니다.

---

## 11. 현재 확인된 정상 동작

- HWP 단독 문서 처리
- HWPX 단독 문서 처리
- HWP/HWPX가 함께 있는 문서의 형식별 처리
- HWP/HWPX Parser 결과 비교
- 문서별 출력 폴더 자동 생성
- Parser JSON 정규화
- Structure Step 1~3 순차 실행
- 구조화 중간 산출물 보존
- 최종 구조화 JSON 기반 Chunk 생성
- Qwen3 Embedding 벡터 생성
- Embedding 벡터와 Metadata 개수 및 차원 검증
- 기존 Embedding 결과 재사용
- 공고별 대표 형식 선택을 통한 중복 Embedding 방지

---

## 12. 현재 확인된 문제

일부 LH 공고문은 문서 본문 대부분이 하나의 큰 외부 표 안에 들어 있습니다.

현재 Step 1의 제목 탐지 로직은 최상위 문단을 중심으로 동작하기 때문에 외부 표의 셀이나 중첩 표 안에 있는 제목을 찾지 못할 수 있습니다.

예:

```text
Ⅰ 공급규모·공급대상 및 공급가격 등
Ⅱ 신청자격 및 선착순 동호지정 절차, 구비서류 등 안내
Ⅲ 기타 유의사항 및 안내사항
```

이 문제가 발생하면 다음과 같은 결과가 생성됩니다.

```text
heading_count = 0
heading_scheme = {}
sections = 0
전체 문서 내용이 intro에 포함
```

후속 영향:

```text
Step 1 제목 탐지 실패
    ↓
Section 계층 생성 실패
    ↓
Step 2 도메인 분류 대상 부족
    ↓
Step 3 표 구조화 대상 부족
    ↓
Chunk가 table_fallback으로 생성
```

이 경우 청킹 자체가 실패한 것은 아닙니다. 앞 단계의 구조화 정보가 부족하기 때문에 원문을 보존하는 fallback 로직이 동작한 상태입니다.

현재 최우선 개선 대상은 다음과 같습니다.

- 표 셀 내부 문단 탐색
- 중첩 표 내부 문단 탐색
- 로마 숫자형 대제목 탐지
- 숫자형 하위 제목 탐지
- 문서 원래 순서를 유지한 Section 재구성

---

## 13. 성능 관련 주의사항

Embedding은 모델 추론 작업이므로 CPU 환경에서 시간이 오래 걸릴 수 있습니다.

실제 처리 시간은 문서 길이, Chunk 수, CPU 성능과 메모리에 따라 달라집니다.

현재 Pipeline은 다음 방식으로 중복 작업을 줄입니다.

- 기존 정상 Embedding 결과 재사용
- Chunk가 변경되지 않은 경우 재생성 생략
- 동일 공고의 HWP/HWPX 중 대표 결과 하나만 Embedding
- Embedding 모델을 한 번 로드한 뒤 여러 문서를 연속 처리

GPU가 있는 환경에서는 자동으로 CUDA를 선택합니다.

---

## 14. GitHub 관리 기준

다음 파일은 자동 생성 결과 또는 로컬 환경 파일이므로 GitHub에 업로드하지 않습니다.

```text
outputs/
chunking/output/
structure/output/
embedding/output/
*.npy
*.npz
*.pt
*.pth
*.safetensors
.env
prj/
__pycache__/
```

테스트 문서 추가 전에는 파일 용량과 외부 공유 가능 여부를 확인해야 합니다.

---

## 15. 다음 개발 단계

현재 우선순위는 다음과 같습니다.

```text
1. 표 셀 및 중첩 표 내부 제목 탐지 개선
2. HWP/HWPX 구조화 결과 재검증
3. Chunk 품질 및 검색 평가셋 작성
4. PostgreSQL + pgvector 저장
5. Retrieval 검색 테스트
6. 근거 기반 RAG 질의응답
7. FastAPI 연결
8. 사용자 및 운영자 화면 연결
```

RAG 답변은 선택한 공고문 범위 안에서 검색하고, 답변 근거가 부족한 경우 임의로 생성하지 않고 근거 부족을 안내하는 방향으로 구현할 예정입니다.

---

## 16. 핵심 요약

팀원이 기본적으로 사용하는 실행 명령은 다음 하나입니다.

```bash
python run_pipeline.py
```

현재 구현 흐름:

```text
HWP/HWPX
 ↓
Parsing
 ↓
Normalization
 ↓
Structure
 ↓
Chunking
 ↓
Embedding
```

현재 가장 중요한 작업은 Pipeline을 새로 연결하는 것이 아니라, **표 내부 제목을 올바르게 인식하여 Section과 표 구조를 안정적으로 복원하는 것**입니다.

자세한 구현 상태와 테스트 결과는 [`docs/PIPELINE_STATUS.md`](docs/PIPELINE_STATUS.md)를 참고하세요.
