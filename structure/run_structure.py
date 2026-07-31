from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from .build_document_step1 import process as process_step1
    from .buid_domain_step2 import process as process_step2
    from .build_table_step3 import process as process_step3
    from .finalize_structure import (
        finalize_step2_file,
        finalize_step3_file,
    )
except ImportError:
    from build_document_step1 import process as process_step1
    from buid_domain_step2 import process as process_step2
    from build_table_step3 import process as process_step3
    from finalize_structure import (
        finalize_step2_file,
        finalize_step3_file,
    )


FINAL_FILENAMES = (
    "step1-1_items.json",
    "step1-2_heading_scheme.json",
    "step1-3_hierarchy.json",
    "step2-1_normalized_titles.json",
    "step2-2_domain_matches.json",
    "step2-3_domain_tagged.json",
    "step2-4_hierarchy_conflicts.json",
    "step2-5_domain_repaired.json",
    "step3-1_table_headers.json",
    "step3-2_table_mappings.json",
    "step3-3_structured_tables.json",
)


def rename_output(
    source_path: str | Path,
    target_path: Path,
) -> Path:
    source = Path(source_path)

    if not source.exists():
        raise FileNotFoundError(
            "Structure 결과 파일을 찾을 수 없습니다.\n"
            f"{source}"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if source.resolve() != target_path.resolve():
        os.replace(source, target_path)

    return target_path


def run_structure_pipeline(
    input_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    if not input_path.exists():
        raise FileNotFoundError(
            "정규화 JSON을 찾을 수 없습니다.\n"
            f"{input_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 72)
    print("Structure Pipeline 시작")
    print("=" * 72)
    print(f"입력: {input_path}")
    print(f"출력: {output_dir}")

    print()
    print("-" * 72)
    print("[Step 1] 문서 계층 구조화")
    print("-" * 72)

    step1_paths = process_step1(
        str(input_path),
        str(output_dir),
    )
    if len(step1_paths) != 3:
        raise RuntimeError(
            "Step 1 결과 파일 수가 예상과 다릅니다."
        )

    step1_final = Path(step1_paths[2])
    if not step1_final.exists():
        raise FileNotFoundError(
            "Step 1 최종 hierarchy 결과를 찾을 수 없습니다.\n"
            f"{step1_final}"
        )

    print()
    print("-" * 72)
    print("[Step 2] 도메인 태깅 및 계층 보정")
    print("-" * 72)

    step2_paths = process_step2(
        str(step1_final),
        str(output_dir),
    )
    if len(step2_paths) != 5:
        raise RuntimeError(
            "Step 2 결과 파일 수가 예상과 다릅니다."
        )

    step2_final = Path(step2_paths[4])
    if not step2_final.exists():
        raise FileNotFoundError(
            "Step 2 최종 domain repaired 결과를 찾을 수 없습니다.\n"
            f"{step2_final}"
        )

    step2_document = finalize_step2_file(step2_final)
    postprocess_info = (
        step2_document
        .get("domain_tagging_method", {})
        .get("postprocessing", {})
    )
    print(
        "[Step 2 보완] 접근성 도메인 보완:",
        postprocess_info.get("resolved_count", 0),
        "건",
    )

    print()
    print("-" * 72)
    print("[Step 3] 표 세부 구조화")
    print("-" * 72)

    step3_paths = process_step3(
        str(step2_final),
        str(output_dir),
    )
    if len(step3_paths) != 3:
        raise RuntimeError(
            "Step 3 결과 파일 수가 예상과 다릅니다."
        )

    step3_final = Path(step3_paths[2])
    if not step3_final.exists():
        raise FileNotFoundError(
            "Step 3 최종 structured tables 결과를 찾을 수 없습니다.\n"
            f"{step3_final}"
        )

    step3_document = finalize_step3_file(step3_final)
    table_postprocess_info = (
        step3_document
        .get("table_structuring_method", {})
        .get("postprocessing", {})
    )
    print(
        "[Step 3 보완] 추가 구조화 표:",
        table_postprocess_info.get("resolved_table_count", 0),
        "개",
    )
    print(
        "[Step 3 보완] 표 인덱스:",
        table_postprocess_info.get("resolved_table_indexes", []),
    )

    generated_paths = [
        *step1_paths,
        *step2_paths,
        *step3_paths,
    ]

    if len(generated_paths) != len(FINAL_FILENAMES):
        raise RuntimeError(
            "전체 Structure 결과 파일 수가 예상과 일치하지 않습니다."
        )

    final_paths: dict[str, Path] = {}

    for source_path, final_filename in zip(
        generated_paths,
        FINAL_FILENAMES,
    ):
        target_path = output_dir / final_filename
        final_paths[final_filename] = rename_output(
            source_path,
            target_path,
        )

    print()
    print("=" * 72)
    print("Structure Pipeline 완료")
    print("=" * 72)

    for filename, path in final_paths.items():
        print(filename)
        print(f"  → {path}")

    print("=" * 72)

    return final_paths


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "정규화된 HWP/HWPX JSON을 "
            "Step 1 → Step 2 → Step 3으로 구조화합니다."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="정규화 JSON 경로",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="구조화 결과 저장 폴더",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    run_structure_pipeline(
        Path(args.input).resolve(),
        Path(args.output_dir).resolve(),
    )


if __name__ == "__main__":
    main()
