import argparse
import os

import jpype


TARGET_CELLS = {
    (2, 0),
    (9, 0),
    (12, 0),
    (20, 0),
    (24, 0),
    (28, 0),
    (42, 0),
    (46, 0),
}


def start_jvm(hwpx_jar_path: str) -> None:
    if jpype.isJVMStarted():
        return

    jar_path = os.path.abspath(hwpx_jar_path)

    if not os.path.exists(jar_path):
        raise FileNotFoundError(
            f"hwpxlib JAR 파일을 찾을 수 없습니다: {jar_path}"
        )

    jpype.startJVM(
        jpype.getDefaultJVMPath(),
        f"-Djava.class.path={jar_path}",
        convertStrings=True,
    )


def print_t_details(t, prefix: str = "") -> None:
    """
    T 객체 내부 구조를 확인합니다.
    """
    class_name = t.getClass().getName()

    print(f"{prefix}T CLASS: {class_name}")

    try:
        print(
            f"{prefix}isOnlyText(): {t.isOnlyText()}"
        )
    except Exception as exc:
        print(
            f"{prefix}isOnlyText() ERROR: {exc}"
        )

    try:
        print(
            f"{prefix}onlyText(): {repr(str(t.onlyText()))}"
        )
    except Exception as exc:
        print(
            f"{prefix}onlyText() ERROR: {exc}"
        )

    try:
        item_count = t.countOfItems()

        print(
            f"{prefix}countOfItems(): {item_count}"
        )

        for item_index in range(item_count):
            item = t.getItem(item_index)

            if item is None:
                print(
                    f"{prefix}  ITEM {item_index}: None"
                )
                continue

            item_class = (
                item
                .getClass()
                .getName()
            )

            print(
                f"{prefix}  ITEM {item_index}: "
                f"{item_class}"
            )

            # Java 객체의 toString 값도 같이 확인
            try:
                print(
                    f"{prefix}    toString(): "
                    f"{repr(str(item))}"
                )
            except Exception as exc:
                print(
                    f"{prefix}    toString ERROR: "
                    f"{exc}"
                )

            # 실제 사용 가능한 메서드 목록 확인
            try:
                methods = (
                    item
                    .getClass()
                    .getMethods()
                )

                method_names = sorted(
                    {
                        str(method.getName())
                        for method in methods
                    }
                )

                print(
                    f"{prefix}    methods: "
                    f"{method_names}"
                )

            except Exception as exc:
                print(
                    f"{prefix}    methods ERROR: "
                    f"{exc}"
                )

    except Exception as exc:
        print(
            f"{prefix}countOfItems/getItem ERROR: {exc}"
        )


def inspect_cell(tc, row: int, col: int) -> None:
    print()
    print("=" * 100)
    print(
        f"TARGET CELL row={row}, col={col}"
    )
    print("=" * 100)

    sublist = tc.subList()

    if sublist is None:
        print("subList 없음")
        return

    print(
        "Paragraph count:",
        sublist.countOfPara(),
    )

    for para_index in range(
        sublist.countOfPara()
    ):
        para = sublist.getPara(
            para_index
        )

        print()
        print(
            f"[PARAGRAPH {para_index}]"
        )

        print(
            "Run count:",
            para.countOfRun(),
        )

        for run_index in range(
            para.countOfRun()
        ):
            run = para.getRun(
                run_index
            )

            print(
                f"  [RUN {run_index}] "
                f"RunItem count="
                f"{run.countOfRunItem()}"
            )

            for item_index in range(
                run.countOfRunItem()
            ):
                item = run.getRunItem(
                    item_index
                )

                if item is None:
                    continue

                class_name = (
                    item
                    .getClass()
                    .getName()
                )

                print(
                    f"    [RUN ITEM {item_index}] "
                    f"{class_name}"
                )

                # T 객체만 상세 분석
                if class_name.endswith(
                    ".paragraph.T"
                ):
                    print_t_details(
                        item,
                        prefix="      ",
                    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hwpx_jar_path",
        required=True,
    )

    parser.add_argument(
        "--file_path",
        required=True,
    )

    args = parser.parse_args()

    start_jvm(
        args.hwpx_jar_path
    )

    file_path = os.path.abspath(
        args.file_path
    )

    HWPXReader = jpype.JClass(
        "kr.dogfoot.hwpxlib.reader.HWPXReader"
    )

    hwpx_file = (
        HWPXReader.fromFilepath(
            file_path
        )
    )

    sections = (
        hwpx_file
        .sectionXMLFileList()
    )

    table_index = 0

    for section_index in range(
        sections.count()
    ):
        section = sections.get(
            section_index
        )

        for para_index in range(
            section.countOfPara()
        ):
            para = section.getPara(
                para_index
            )

            for run_index in range(
                para.countOfRun()
            ):
                run = para.getRun(
                    run_index
                )

                for run_item_index in range(
                    run.countOfRunItem()
                ):
                    item = run.getRunItem(
                        run_item_index
                    )

                    if item is None:
                        continue

                    class_name = (
                        item
                        .getClass()
                        .getName()
                    )

                    if not class_name.endswith(
                        ".Table"
                    ):
                        continue

                    # 비교 결과상 실제 문제 셀은 Table 1
                    if table_index == 1:

                        for tr_index in range(
                            item.countOfTr()
                        ):
                            tr = item.getTr(
                                tr_index
                            )

                            for tc_index in range(
                                tr.countOfTc()
                            ):
                                tc = tr.getTc(
                                    tc_index
                                )

                                addr = (
                                    tc.cellAddr()
                                )

                                if addr is None:
                                    continue

                                row = int(
                                    addr.rowAddr()
                                )

                                col = int(
                                    addr.colAddr()
                                )

                                if (
                                    row,
                                    col,
                                ) in TARGET_CELLS:
                                    inspect_cell(
                                        tc,
                                        row,
                                        col,
                                    )

                    table_index += 1


if __name__ == "__main__":
    main()