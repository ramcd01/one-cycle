import subprocess
import sys
from collections import defaultdict
from pathlib import Path


# ============================================================
# 프로젝트 기본 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PARSER_DIR = BASE_DIR / "parser"
NORMALIZER_DIR = BASE_DIR / "normalizer"

TEST_DOCUMENT_DIR = BASE_DIR / "test_documents"

OUTPUT_DIR = BASE_DIR / "outputs"
NORMALIZED_OUTPUT_DIR = OUTPUT_DIR / "normalized"


# ============================================================
# Parser 파일 경로
# ============================================================

HWP_PARSER_PATH = (
    PARSER_DIR
    / "hwp_parser.py"
)

HWPX_PARSER_PATH = (
    PARSER_DIR
    / "hwpx_parser.py"
)

COMPARE_PARSER_PATH = (
    PARSER_DIR
    / "compare_parsers.py"
)

NORMALIZER_PATH = (
    NORMALIZER_DIR
    / "document_normalizer.py"
)


# ============================================================
# JAR 파일 경로
# ============================================================

HWP_JAR_PATH = (
    BASE_DIR
    / "libs"
    / "hwp"
    / "hwplib-1.1.8.jar"
)

HWPX_JAR_PATH = (
    BASE_DIR
    / "libs"
    / "hwpx"
    / "hwpxlib-1.0.8.jar"
)


# ============================================================
# 기본 폴더 생성
# ============================================================

def ensure_directories() -> None:
    """
    Pipeline 실행에 필요한 출력 폴더를 생성합니다.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    NORMALIZED_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# 필수 파일 확인
# ============================================================

def validate_project_files() -> bool:
    """
    Pipeline 실행에 필요한 Python 파일과
    JAR 파일이 존재하는지 확인합니다.
    """

    required_files = [
        HWP_PARSER_PATH,
        HWPX_PARSER_PATH,
        COMPARE_PARSER_PATH,
        NORMALIZER_PATH,
        HWP_JAR_PATH,
        HWPX_JAR_PATH,
    ]

    missing_files = []

    for file_path in required_files:
        if not file_path.exists():
            missing_files.append(
                file_path
            )

    if not TEST_DOCUMENT_DIR.exists():
        print()
        print(
            "[ERROR] test_documents 폴더가 없습니다."
        )
        print(
            TEST_DOCUMENT_DIR
        )

        return False

    if missing_files:
        print()
        print(
            "[ERROR] 필요한 파일을 찾을 수 없습니다."
        )

        for file_path in missing_files:
            print(
                f"- {file_path}"
            )

        return False

    return True


# ============================================================
# 문서 ID 생성
# ============================================================

def get_document_id(
    file_path: Path,
) -> str:
    """
    테스트 문서의 ID를 결정합니다.

    예:

    test_documents/
        announcement_001/
            example.hwp

    → announcement_001


    test_documents/
        example.hwp

    → example
    """

    relative_path = (
        file_path.relative_to(
            TEST_DOCUMENT_DIR
        )
    )

    # 하위 폴더에 들어 있는 경우
    if len(
        relative_path.parts
    ) > 1:

        return relative_path.parts[
            0
        ]

    # test_documents 바로 아래에 있는 경우
    return file_path.stem


# ============================================================
# 테스트 문서 자동 탐색
# ============================================================

def find_test_documents() -> dict:
    """
    test_documents 및 모든 하위 폴더에서

    .hwp
    .hwpx

    파일을 자동으로 탐색합니다.
    """

    hwp_files = sorted(
        path
        for path
        in TEST_DOCUMENT_DIR.rglob(
            "*"
        )
        if (
            path.is_file()
            and
            path.suffix.lower()
            ==
            ".hwp"
        )
    )

    hwpx_files = sorted(
        path
        for path
        in TEST_DOCUMENT_DIR.rglob(
            "*"
        )
        if (
            path.is_file()
            and
            path.suffix.lower()
            ==
            ".hwpx"
        )
    )

    return {
        "hwp":
            hwp_files,

        "hwpx":
            hwpx_files,
    }


# ============================================================
# 테스트 문서 그룹 생성
# ============================================================

def group_test_documents() -> dict:
    """
    문서를 document_id 기준으로 그룹화합니다.

    예:

    announcement_001
        ├─ hwp
        └─ hwpx
    """

    documents = (
        find_test_documents()
    )

    groups = defaultdict(
        lambda: {
            "hwp": [],
            "hwpx": [],
        }
    )

    for file_path in documents[
        "hwp"
    ]:

        document_id = (
            get_document_id(
                file_path
            )
        )

        groups[
            document_id
        ][
            "hwp"
        ].append(
            file_path
        )

    for file_path in documents[
        "hwpx"
    ]:

        document_id = (
            get_document_id(
                file_path
            )
        )

        groups[
            document_id
        ][
            "hwpx"
        ].append(
            file_path
        )

    return dict(
        sorted(
            groups.items()
        )
    )


# ============================================================
# 테스트 문서 현황 출력
# ============================================================

def print_document_summary() -> None:
    """
    자동 탐색된 테스트 문서 현황을 출력합니다.
    """

    documents = (
        find_test_documents()
    )

    groups = (
        group_test_documents()
    )

    pair_count = 0

    for data in groups.values():

        if (
            data["hwp"]
            and
            data["hwpx"]
        ):
            pair_count += 1

    print()
    print(
        "=" * 70
    )
    print(
        "테스트 문서 자동 탐색 결과"
    )
    print(
        "=" * 70
    )

    print(
        f"HWP  파일 : "
        f"{len(documents['hwp'])}개"
    )

    print(
        f"HWPX 파일 : "
        f"{len(documents['hwpx'])}개"
    )

    print(
        f"문서 그룹 : "
        f"{len(groups)}개"
    )

    print(
        f"비교 가능 그룹 : "
        f"{pair_count}개"
    )

    print()

    for document_id, data in groups.items():

        hwp_status = (
            f"{len(data['hwp'])}개"
            if data["hwp"]
            else
            "없음"
        )

        hwpx_status = (
            f"{len(data['hwpx'])}개"
            if data["hwpx"]
            else
            "없음"
        )

        print(
            f"- {document_id}"
        )

        print(
            f"    HWP  : {hwp_status}"
        )

        print(
            f"    HWPX : {hwpx_status}"
        )


# ============================================================
# 외부 Python 스크립트 실행
# ============================================================

def run_command(
    command: list[str],
) -> bool:
    """
    Python 스크립트를 subprocess로 실행합니다.

    현재 실행 중인 Python Interpreter를 사용합니다.
    """

    print()

    print(
        "-" * 70
    )

    print(
        "실행:"
    )

    print(
        " ".join(
            str(item)
            for item
            in command
        )
    )

    print(
        "-" * 70
    )

    try:

        subprocess.run(
            command,
            cwd=str(
                BASE_DIR
            ),
            check=True,
        )

        return True

    except subprocess.CalledProcessError as error:

        print()
        print(
            "[ERROR] 실행 실패"
        )

        print(
            f"Return Code: "
            f"{error.returncode}"
        )

        return False

    except Exception as error:

        print()
        print(
            "[ERROR] 예외 발생"
        )

        print(
            error
        )

        return False


# ============================================================
# 출력 JSON 경로 생성
# ============================================================

def get_output_path(
    document_id: str,
    document_format: str,
) -> Path:
    """
    Parser 출력 JSON 경로를 생성합니다.

    예:

    announcement_001_hwp.json
    announcement_001_hwpx.json
    """

    return (
        OUTPUT_DIR
        /
        (
            f"{document_id}"
            f"_"
            f"{document_format}"
            f".json"
        )
    )


# ============================================================
# HWP 단일 파일 파싱
# ============================================================

def parse_hwp_file(
    file_path: Path,
    document_id: str,
) -> bool:

    output_path = (
        get_output_path(
            document_id,
            "hwp",
        )
    )

    print()
    print(
        f"[HWP 파싱]"
    )
    print(
        f"문서 ID: {document_id}"
    )
    print(
        f"입력: {file_path}"
    )
    print(
        f"출력: {output_path}"
    )

    command = [
        sys.executable,

        str(
            HWP_PARSER_PATH
        ),

        "--hwp_jar_path",

        str(
            HWP_JAR_PATH
        ),

        "--file_path",

        str(
            file_path
        ),

        "--output_path",

        str(
            output_path
        ),
    ]

    return run_command(
        command
    )


# ============================================================
# HWPX 단일 파일 파싱
# ============================================================

def parse_hwpx_file(
    file_path: Path,
    document_id: str,
) -> bool:

    output_path = (
        get_output_path(
            document_id,
            "hwpx",
        )
    )

    print()
    print(
        f"[HWPX 파싱]"
    )
    print(
        f"문서 ID: {document_id}"
    )
    print(
        f"입력: {file_path}"
    )
    print(
        f"출력: {output_path}"
    )

    command = [
        sys.executable,

        str(
            HWPX_PARSER_PATH
        ),

        "--hwpx_jar_path",

        str(
            HWPX_JAR_PATH
        ),

        "--file_path",

        str(
            file_path
        ),

        "--output_path",

        str(
            output_path
        ),
    ]

    return run_command(
        command
    )


# ============================================================
# HWP 전체 파싱
# ============================================================

def run_hwp_parser() -> None:
    """
    발견된 모든 HWP 파일을 파싱합니다.
    """

    groups = (
        group_test_documents()
    )

    targets = []

    for document_id, data in groups.items():

        for file_path in data[
            "hwp"
        ]:

            targets.append(
                (
                    document_id,
                    file_path,
                )
            )

    if not targets:

        print()
        print(
            "[안내] HWP 파일이 없습니다."
        )

        return

    print()
    print(
        "=" * 70
    )
    print(
        "HWP 전체 파싱"
    )
    print(
        "=" * 70
    )

    print(
        f"대상: {len(targets)}개"
    )

    success = 0
    fail = 0

    for (
        document_id,
        file_path,
    ) in targets:

        result = (
            parse_hwp_file(
                file_path,
                document_id,
            )
        )

        if result:
            success += 1

        else:
            fail += 1

    print()
    print(
        f"HWP 파싱 완료 "
        f"- 성공: {success}, "
        f"실패: {fail}"
    )


# ============================================================
# HWPX 전체 파싱
# ============================================================

def run_hwpx_parser() -> None:
    """
    발견된 모든 HWPX 파일을 파싱합니다.
    """

    groups = (
        group_test_documents()
    )

    targets = []

    for document_id, data in groups.items():

        for file_path in data[
            "hwpx"
        ]:

            targets.append(
                (
                    document_id,
                    file_path,
                )
            )

    if not targets:

        print()
        print(
            "[안내] HWPX 파일이 없습니다."
        )

        return

    print()
    print(
        "=" * 70
    )
    print(
        "HWPX 전체 파싱"
    )
    print(
        "=" * 70
    )

    print(
        f"대상: {len(targets)}개"
    )

    success = 0
    fail = 0

    for (
        document_id,
        file_path,
    ) in targets:

        result = (
            parse_hwpx_file(
                file_path,
                document_id,
            )
        )

        if result:
            success += 1

        else:
            fail += 1

    print()
    print(
        f"HWPX 파싱 완료 "
        f"- 성공: {success}, "
        f"실패: {fail}"
    )


# ============================================================
# 모든 문서 파싱
# ============================================================

def run_all_parsers() -> None:

    run_hwp_parser()

    run_hwpx_parser()


# ============================================================
# HWP / HWPX Parser 결과 자동 비교
# ============================================================

def run_compare() -> None:
    """
    동일 document_id의

    *_hwp.json
    *_hwpx.json

    파일을 자동으로 찾아 비교합니다.
    """

    groups = (
        group_test_documents()
    )

    comparison_targets = []

    for document_id, data in groups.items():

        if not (
            data["hwp"]
            and
            data["hwpx"]
        ):
            continue

        hwp_json = (
            get_output_path(
                document_id,
                "hwp",
            )
        )

        hwpx_json = (
            get_output_path(
                document_id,
                "hwpx",
            )
        )

        if (
            hwp_json.exists()
            and
            hwpx_json.exists()
        ):

            comparison_targets.append(
                (
                    document_id,
                    hwp_json,
                    hwpx_json,
                )
            )

    if not comparison_targets:

        print()
        print(
            "[안내] 비교 가능한 Parser 결과가 없습니다."
        )
        print(
            "먼저 HWP/HWPX 파싱을 실행하세요."
        )

        return

    print()
    print(
        "=" * 70
    )
    print(
        "HWP / HWPX Parser 결과 비교"
    )
    print(
        "=" * 70
    )

    for (
        document_id,
        hwp_json,
        hwpx_json,
    ) in comparison_targets:

        print()
        print(
            f"[비교] {document_id}"
        )

        command = [
            sys.executable,

            str(
                COMPARE_PARSER_PATH
            ),

            "--hwp",

            str(
                hwp_json
            ),

            "--hwpx",

            str(
                hwpx_json
            ),
        ]

        run_command(
            command
        )


# ============================================================
# 정규화 대상 JSON 자동 탐색
# ============================================================

def find_raw_json_files() -> list[Path]:
    """
    outputs 폴더 바로 아래의 Parser JSON만 탐색합니다.

    outputs/normalized 내부 파일은 제외됩니다.
    """

    files = []

    for file_path in OUTPUT_DIR.glob(
        "*.json"
    ):

        if not file_path.is_file():
            continue

        if (
            file_path.name.endswith(
                "_hwp.json"
            )
            or
            file_path.name.endswith(
                "_hwpx.json"
            )
        ):

            files.append(
                file_path
            )

    return sorted(
        files
    )


# ============================================================
# 단일 JSON 정규화
# ============================================================

def normalize_file(
    input_path: Path,
) -> bool:

    output_path = (
        NORMALIZED_OUTPUT_DIR
        /
        input_path.name
    )

    command = [
        sys.executable,

        str(
            NORMALIZER_PATH
        ),

        "--input",

        str(
            input_path
        ),

        "--output",

        str(
            output_path
        ),
    ]

    return run_command(
        command
    )


# ============================================================
# 전체 정규화
# ============================================================

def normalize_all() -> None:

    files = (
        find_raw_json_files()
    )

    if not files:

        print()
        print(
            "[안내] 정규화할 Parser JSON이 없습니다."
        )

        print(
            "먼저 Parser를 실행하세요."
        )

        return

    print()
    print(
        "=" * 70
    )
    print(
        "전체 JSON 정규화"
    )
    print(
        "=" * 70
    )

    print(
        f"대상: {len(files)}개"
    )

    success = 0
    fail = 0

    for file_path in files:

        print()
        print(
            f"[정규화] "
            f"{file_path.name}"
        )

        result = (
            normalize_file(
                file_path
            )
        )

        if result:
            success += 1

        else:
            fail += 1

    print()
    print(
        "=" * 70
    )

    print(
        "정규화 완료"
    )

    print(
        f"성공: {success}"
    )

    print(
        f"실패: {fail}"
    )

    print(
        f"출력: "
        f"{NORMALIZED_OUTPUT_DIR}"
    )


# ============================================================
# 전체 Pipeline
# ============================================================

def run_full_pipeline() -> None:
    """
    전체 Pipeline 실행.

    1. HWP 파싱
    2. HWPX 파싱
    3. Parser 결과 비교
    4. 정규화
    """

    print()
    print(
        "=" * 70
    )
    print(
        "전체 Document Pipeline 시작"
    )
    print(
        "=" * 70
    )

    run_all_parsers()

    run_compare()

    normalize_all()

    print()
    print(
        "=" * 70
    )
    print(
        "전체 Document Pipeline 완료"
    )
    print(
        "=" * 70
    )


# ============================================================
# 메뉴
# ============================================================

def print_menu() -> None:

    print()
    print(
        "=" * 70
    )
    print(
        "Hancom AI Document Pipeline"
    )
    print(
        "=" * 70
    )

    print(
        "1. 테스트 문서 목록 확인"
    )

    print(
        "2. HWP 전체 파싱"
    )

    print(
        "3. HWPX 전체 파싱"
    )

    print(
        "4. HWP + HWPX 전체 파싱"
    )

    print(
        "5. HWP / HWPX Parser 결과 비교"
    )

    print(
        "6. Parser JSON 전체 정규화"
    )

    print(
        "7. 전체 Pipeline 실행"
    )

    print(
        "0. 종료"
    )

    print(
        "=" * 70
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    ensure_directories()

    if not validate_project_files():

        print()
        print(
            "Pipeline을 실행할 수 없습니다."
        )

        return

    # 프로그램 시작 시 자동 탐색 결과 출력
    print_document_summary()

    while True:

        print_menu()

        choice = input(
            "선택: "
        ).strip()

        if choice == "1":

            print_document_summary()

        elif choice == "2":

            run_hwp_parser()

        elif choice == "3":

            run_hwpx_parser()

        elif choice == "4":

            run_all_parsers()

        elif choice == "5":

            run_compare()

        elif choice == "6":

            normalize_all()

        elif choice == "7":

            run_full_pipeline()

        elif choice == "0":

            print()
            print(
                "Pipeline을 종료합니다."
            )

            break

        else:

            print()
            print(
                "[안내] 올바른 번호를 입력하세요."
            )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()