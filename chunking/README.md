# Chunking Test

`structure` 단계에서 생성한 최종 JSON을 검색 및 임베딩에 사용할 청크 단위로 변환하는 테스트 코드입니다.

## 폴더 구성

```text
chunking/
├── build_chunks.py
└── output/
```

## 입력 파일

```text
*_step3-3_structured_tables.json
```

## 실행

```bash
python build_chunks.py
```

실행 후 파일 선택 창에서 3단계 최종 JSON을 선택합니다.

## 출력 파일

```text
output/*_step4_chunks.json
```

## 청킹 규칙

```text
paragraph
→ 같은 section 안에서 연속된 문단을 하나로 묶음
→ 너무 길면 글자 수 기준으로 분할

row_records 표
→ 구조화된 record 한 행당 하나의 table_row 청크 생성

key_value 표
→ key-value 한 쌍당 하나의 table_key_value 청크 생성

unresolved / skipped / 구조화 정보가 없는 표
→ 원본 cells를 행과 열 순서대로 합쳐 table_fallback 청크 생성
```

모든 청크에는 다음 출처 정보가 메타데이터로 저장됩니다.

```text
문서명
section_id
section_path
domain
content_index
table_index
row_index
표 구조화 상태
원본 source
```

현재 코드는 청킹 구현 가능성을 확인하기 위한 테스트 버전입니다.
