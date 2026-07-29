# Document Pipeline 현재 구현 상태

## 1. 개요

현재 HWP/HWPX 공고문을 입력받아 파싱, 정규화, 구조화, 청킹, 임베딩까지 수행하는 문서 처리 Pipeline이 연결되어 있습니다.

```text
HWP / HWPX
    ↓
01_parsed
    ↓
02_normalized
    ↓
03_structured
    ↓
04_chunks
    ↓
05_embeddings
```

현재 Pipeline은 로컬 테스트 환경을 기준으로 구현되어 있습니다.

---

## 2. 전체 Pipeline 실행

프로젝트 루트에서 다음 명령을 실행합니다.

```bash
python run_pipeline.py
```

실행 메뉴는 다음과 같습니다.

```text
1. 테스트 문서 현황 확인
2. HWP 전체 파싱
3. HWPX 전체 파싱
4. 분석 가능한 문서 전체 파싱
5. HWP/HWPX 비교 가능한 문서 비교
6. Parser JSON 전체 정규화
7. 정규화 JSON 전체 구조화
8. 최종 구조화 JSON 전체 청킹
9. Chunk JSON 전체 임베딩
10. 전체 Pipeline 실행
0. 종료
```

각 단계만 별도로 실행할 수 있으며, `10번`을 선택하면 현재 연결된 전체 Pipeline을 순차적으로 실행합니다.

---

## 3. 입력 문서 구조

테스트 문서는 다음 경로에서 자동으로 탐색합니다.

```text
test_documents/
├─ announcement_001/
├─ announcement_002/
├─ announcement_003/
└─ announcement_004/
```

각 공고 폴더에는 HWP 또는 HWPX 파일이 들어갈 수 있습니다.

```text
test_documents/<document_id>/
├─ 공고문.hwp
└─ 공고문.hwpx
```

현재 PDF 파일은 문서 처리 대상에 포함하지 않습니다.

공고 폴더에 HWP만 있으면 HWP만 처리하고, HWPX만 있으면 HWPX만 처리합니다. 두 형식이 모두 있으면 각각 처리한 뒤 비교할 수 있습니다.

---

## 4. 출력 구조

처리 결과는 문서별로 다음 구조에 저장됩니다.

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
│  │
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
   │
   └─ hwpx/
      ├─ embeddings.npy
      └─ metadata.json
```

입력 문서에 존재하지 않는 형식의 출력 폴더는 생성하지 않습니다.

예를 들어 HWPX 파일만 있는 공고는 다음과 같이 처리됩니다.

```text
outputs/<document_id>/
├─ 01_parsed/
│  └─ hwpx.json
├─ 02_normalized/
│  └─ hwpx.json
├─ 03_structured/
│  └─ hwpx/
├─ 04_chunks/
│  └─ hwpx/
└─ 05_embeddings/
   └─ hwpx/
```

---

## 5. 현재 확인된 정상 동작

현재까지 다음 동작을 확인했습니다.

- HWP 단독 문서 처리
- HWPX 단독 문서 처리
- HWP/HWPX가 함께 있는 문서의 형식별 처리
- HWP/HWPX Parser 결과 비교
- 문서별 출력 폴더 자동 생성
- Parser JSON 정규화
- Structure Step 1부터 Step 3까지 자동 순차 실행
- 구조화 중간 산출물 11개 보존
- 최종 구조화 JSON 기반 Chunk 생성
- Qwen3 Embedding 모델을 이용한 벡터 생성
- 임베딩 벡터와 Metadata 청크 개수 검증
- 임베딩 벡터 차원 검증

현재 사용 중인 임베딩 모델은 다음과 같습니다.

```text
Qwen/Qwen3-Embedding-0.6B
```

생성되는 임베딩 벡터의 차원은 다음과 같습니다.

```text
1024
```

---

## 6. 현재 확인된 구조화 문제

일부 LH HWP/HWPX 공고문은 문서의 본문 대부분이 하나의 큰 외부 표 안에 들어 있습니다.

현재 Step 1 구조화 로직은 주로 최상위 문단을 기준으로 제목 후보를 탐색합니다. 따라서 외부 표의 셀 또는 중첩 표 안에 있는 제목을 정상적으로 인식하지 못하는 경우가 있습니다.

실제 문서에는 다음과 같은 제목이 존재합니다.

```text
Ⅰ 공급규모·공급대상 및 공급가격 등
Ⅱ 신청자격 및 선착순 동호지정 절차, 구비서류 등 안내
Ⅲ 기타 유의사항 및 안내사항
```

하지만 해당 제목이 외부 표 내부에 있는 경우 현재 결과가 다음과 같이 생성될 수 있습니다.

```text
heading_count = 0
heading_scheme = {}
sections = 0
전체 문서 내용이 intro에 포함
```

이 문제가 발생하면 이후 단계에도 영향을 줍니다.

```text
Step 1 제목 탐지 실패
    ↓
Section 계층 생성 실패
    ↓
Step 2 Domain 분류 대상 부족
    ↓
Step 3 표 구조화 대상 부족
    ↓
Chunk가 table_fallback으로 생성
```

실제 확인된 Chunk 결과는 다음과 같습니다.

```text
chunk_type = table_fallback
section_id = intro
section_title = 문서 도입부
table_status = missing
```

청킹 자체가 실패한 것은 아닙니다. 앞 단계에서 구조화된 표 정보가 없기 때문에 원문 손실을 방지하기 위한 fallback 로직이 작동한 상태입니다.

---

## 7. 다음 우선 작업

다음 작업에서는 Step 1의 제목 탐지 범위를 확장해야 합니다.

주요 개선 대상은 다음과 같습니다.

1. 최상위 문단뿐 아니라 표 셀 내부 문단 탐색
2. 중첩 표 내부의 문단 탐색
3. 표 내부의 로마 숫자 제목 탐지
4. 숫자형 하위 제목 탐지
5. 문서 원래 순서를 유지한 제목 후보 생성
6. 제목과 제목 아래 콘텐츠의 Section 재구성

목표 구조는 다음과 같습니다.

```text
intro
sections
├─ Ⅰ 공급규모·공급대상 및 공급가격 등
│  ├─ 1. 공급규모
│  ├─ 2. 공급대상
│  └─ 3. 공급가격
│
├─ Ⅱ 신청자격 및 선착순 동호지정 절차, 구비서류 등 안내
│  ├─ 신청자격
│  ├─ 일정 및 장소
│  └─ 구비서류
│
└─ Ⅲ 기타 유의사항 및 안내사항
```

---

## 8. 임베딩 처리 시 주의사항

현재 로컬 환경에서는 CUDA가 아닌 CPU를 사용하고 있습니다.

```text
device = cpu
```

Qwen3 Embedding 모델을 CPU로 실행하면 문서의 청크 수에 따라 처리 시간이 크게 증가할 수 있습니다.

실제 테스트에서는 다음과 같은 시간이 확인되었습니다.

```text
13개 Chunk  → 약 5분 30초
91개 Chunk  → 약 40분
```

따라서 로컬 환경에서는 다음 방식으로 개선할 예정입니다.

- 이미 생성된 정상 임베딩 결과 재사용
- 변경되지 않은 Chunk 재임베딩 방지
- 공고별 대표 문서 형식 하나만 서비스용 임베딩 대상으로 선택
- HWP/HWPX 비교 결과는 청킹 단계까지 보존
- 실제 운영 환경에서는 GPU 기반 임베딩 처리 검토

현재 HWP와 HWPX가 모두 존재하는 경우에는 형식별 결과 비교를 위해 두 결과가 모두 생성될 수 있습니다.

---

## 9. GitHub에 포함하지 않는 파일

다음 파일과 폴더는 GitHub에 업로드하지 않습니다.

```text
outputs/
*.npy
*.npz
*.pt
*.pth
*.safetensors
.env
prj/
__pycache__/
```

`outputs`에는 자동 생성 결과가 들어 있으므로 소스코드와 분리합니다.

테스트 결과를 팀원과 공유해야 하는 경우에는 전체 `outputs`를 저장소에 올리지 않고, 필요한 JSON 일부를 별도 문서나 공유 저장소를 통해 전달합니다.

---

## 10. 팀 협업 방식

현재 Pipeline 상태는 체크포인트 브랜치에 보존합니다.

```text
feature/document-pipeline
```

이 브랜치에는 다음 내용을 포함합니다.

- 현재까지 연결된 전체 Pipeline
- Parser, Normalizer, Structure, Chunking, Embedding 실행 코드
- 출력 경로 관리 코드
- 현재 구현 상태 문서
- 알려진 문제 기록

팀원은 체크포인트 브랜치에서 직접 동시에 수정하지 않고, 작업 목적에 따라 별도 브랜치를 생성합니다.

예시:

```text
fix/nested-table-heading
feature/rag-search
feature/fastapi
feature/admin-api
```

각 작업 완료 후 Pull Request를 통해 통합합니다.