from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

PARSER_DIR = BASE_DIR / "parser"
LIBS_DIR = BASE_DIR / "libs"
TEST_DOCUMENTS_DIR = BASE_DIR / "test_documents"
OUTPUTS_DIR = BASE_DIR / "outputs"

HWP_PARSER = PARSER_DIR / "hwp_parser.py"
HWPX_PARSER = PARSER_DIR / "hwpx_parser.py"
COMPARE_PARSER = PARSER_DIR / "compare_parsers.py"

HWP_JAR = LIBS_DIR / "hwp" / "hwplib-1.1.8.jar"
HWPX_JAR = LIBS_DIR / "hwpx" / "hwpxlib-1.0.8.jar"


DOCUMENTS = {
    "1": {
        "id": "announcement_001",
    },
    "2": {
        "id": "announcement_002",
    },
    "3": {
        "id": "announcement_003",
    },
}


def find_single_file(folder: Path, suffix: str) -> Path:
    """지정 폴더에서 특정 확장자 파일 하나를 찾습니다."""
    files = list(folder.glob(f"*{suffix}"))

    if not files:
        raise FileNotFoundError(
            f"{folder} 폴더에서 {suffix} 파일을 찾을 수 없습니다."
        )

    if len(files) > 1:
        raise RuntimeError(
            f"{folder} 폴더에 {suffix} 파일이 여러 개 있습니다.\n"
            f"파일 목록: {[file.name for file in files]}"
        )

    return files[0]


def run_command(command: list[str], title: str) -> bool:
    """명령어를 실행하고 성공 여부를 반환합니다."""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    try:
        subprocess.run(
            command,
            check=True,
        )
        return True

    except subprocess.CalledProcessError as exc:
        print()
        print(f"[ERROR] 실행 실패: {title}")
        print(f"종료 코드: {exc.returncode}")
        return False


def get_document_paths(document_id: str) -> dict[str, Path]:
    """선택한 공고문의 입력 및 출력 경로를 구성합니다."""
    document_dir = TEST_DOCUMENTS_DIR / document_id

    if not document_dir.exists():
        raise FileNotFoundError(
            f"테스트 문서 폴더를 찾을 수 없습니다: {document_dir}"
        )

    hwp_file = find_single_file(document_dir, ".hwp")
    hwpx_file = find_single_file(document_dir, ".hwpx")

    return {
        "hwp": hwp_file,
        "hwpx": hwpx_file,
        "hwp_output": OUTPUTS_DIR / f"{document_id}_hwp.json",
        "hwpx_output": OUTPUTS_DIR / f"{document_id}_hwpx.json",
    }


def run_hwp_parser(document_id: str, paths: dict[str, Path]) -> bool:
    """HWP Parser를 실행합니다."""
    command = [
        sys.executable,
        str(HWP_PARSER),
        "--hwp_jar_path",
        str(HWP_JAR),
        "--file_path",
        str(paths["hwp"]),
        "--output_path",
        str(paths["hwp_output"]),
    ]

    return run_command(
        command,
        f"{document_id} - HWP 파싱",
    )


def run_hwpx_parser(document_id: str, paths: dict[str, Path]) -> bool:
    """HWPX Parser를 실행합니다."""
    command = [
        sys.executable,
        str(HWPX_PARSER),
        "--hwpx_jar_path",
        str(HWPX_JAR),
        "--file_path",
        str(paths["hwpx"]),
        "--output_path",
        str(paths["hwpx_output"]),
    ]

    return run_command(
        command,
        f"{document_id} - HWPX 파싱",
    )


def run_compare(document_id: str, paths: dict[str, Path]) -> bool:
    """HWP/HWPX JSON 비교 스크립트를 실행합니다."""
    if not paths["hwp_output"].exists():
        print(
            f"[ERROR] HWP 결과 파일이 없습니다: "
            f"{paths['hwp_output']}"
        )
        return False

    if not paths["hwpx_output"].exists():
        print(
            f"[ERROR] HWPX 결과 파일이 없습니다: "
            f"{paths['hwpx_output']}"
        )
        return False

    command = [
        sys.executable,
        str(COMPARE_PARSER),
        "--hwp",
        str(paths["hwp_output"]),
        "--hwpx",
        str(paths["hwpx_output"]),
    ]

    return run_command(
        command,
        f"{document_id} - HWP/HWPX 비교",
    )


def print_main_menu() -> None:
    print()
    print("=" * 80)
    print("DDOK Parser Test")
    print("=" * 80)
    print()
    print("테스트할 문서를 선택하세요.")
    print()
    print("1. announcement_001")
    print("2. announcement_002")
    print("3. announcement_003")
    print("0. 종료")
    print()


def print_action_menu() -> None:
    print()
    print("실행할 작업을 선택하세요.")
    print()
    print("1. HWP 파싱")
    print("2. HWPX 파싱")
    print("3. HWP + HWPX 모두 파싱")
    print("4. HWP/HWPX 결과 비교")
    print("5. 전체 실행 (HWP → HWPX → 비교)")
    print("0. 이전 메뉴")
    print()


def run_document_menu(document_id: str) -> None:
    try:
        paths = get_document_paths(document_id)
    except (FileNotFoundError, RuntimeError) as exc:
        print()
        print(f"[ERROR] {exc}")
        return

    while True:
        print()
        print(f"선택된 문서: {document_id}")
        print_action_menu()

        action = input("선택: ").strip()

        if action == "0":
            return

        if action == "1":
            run_hwp_parser(document_id, paths)

        elif action == "2":
            run_hwpx_parser(document_id, paths)

        elif action == "3":
            hwp_success = run_hwp_parser(document_id, paths)

            if hwp_success:
                run_hwpx_parser(document_id, paths)

        elif action == "4":
            run_compare(document_id, paths)

        elif action == "5":
            hwp_success = run_hwp_parser(document_id, paths)

            if not hwp_success:
                continue

            hwpx_success = run_hwpx_parser(document_id, paths)

            if not hwpx_success:
                continue

            run_compare(document_id, paths)

        else:
            print()
            print("잘못된 입력입니다. 0~5 중에서 선택하세요.")


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        print_main_menu()

        choice = input("선택: ").strip()

        if choice == "0":
            print()
            print("DDOK Parser Test를 종료합니다.")
            return

        document = DOCUMENTS.get(choice)

        if document is None:
            print()
            print("잘못된 입력입니다. 0~3 중에서 선택하세요.")
            continue

        run_document_menu(document["id"])


if __name__ == "__main__":
    main()