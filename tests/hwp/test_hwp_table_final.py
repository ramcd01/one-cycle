import os
import jpype


JAR_PATH = r".\hwplib-1.1.8.jar"
HWP_PATH = r".\(정정)고양창릉S-4블록공공분양입주자모집공고문.hwp"


def start_jvm():
    if not jpype.isJVMStarted():
        jpype.startJVM(
            jpype.getDefaultJVMPath(),
            f"-Djava.class.path={os.path.abspath(JAR_PATH)}",
            convertStrings=True,
        )


def get_size(collection):
    try:
        return collection.size()
    except AttributeError:
        return len(collection)


def get_item(collection, index):
    try:
        return collection.get(index)
    except AttributeError:
        return collection[index]


def main():
    start_jvm()

    HWPReader = jpype.JPackage(
        "kr.dogfoot.hwplib.reader"
    ).HWPReader

    hwp_file = HWPReader.fromFile(
        os.path.abspath(HWP_PATH)
    )

    sections = hwp_file.getBodyText().getSectionList()

    table_index = 0

    for section_index in range(get_size(sections)):
        section = get_item(sections, section_index)

        paragraphs = section.getParagraphs()

        for paragraph_index in range(len(paragraphs)):
            paragraph = paragraphs[paragraph_index]

            # Control 목록
            try:
                controls = paragraph.getControlList()
            except Exception:
                try:
                    controls = paragraph.getControls()
                except Exception:
                    continue

            if controls is None:
                continue

            for control_index in range(get_size(controls)):
                control = get_item(
                    controls,
                    control_index
                )

                class_name = control.getClass().getName()

                if not class_name.endswith("ControlTable"):
                    continue

                print()
                print("=" * 100)
                print(
                    f"TABLE {table_index} | "
                    f"Section {section_index} | "
                    f"Paragraph {paragraph_index}"
                )
                print("=" * 100)

                rows = control.getRowList()

                for row_index in range(get_size(rows)):
                    row = get_item(rows, row_index)
                    cells = row.getCellList()

                    print(f"\n[ROW LIST INDEX {row_index}]")

                    for cell_index in range(get_size(cells)):
                        cell = get_item(
                            cells,
                            cell_index
                        )

                        # 셀 위치 / 병합 정보
                        header = cell.getListHeader()

                        actual_row = header.getRowIndex()
                        actual_col = header.getColIndex()

                        row_span = header.getRowSpan()
                        col_span = header.getColSpan()

                        # 셀 텍스트
                        paragraph_list = (
                            cell.getParagraphList()
                        )

                        try:
                            text = (
                                paragraph_list
                                .getNormalString()
                            )
                        except Exception:
                            text = ""

                        # 보기 편하게 줄바꿈 축약
                        if text:
                            text = (
                                str(text)
                                .replace("\r", " ")
                                .replace("\n", " ")
                                .strip()
                            )

                        print(
                            f"  Cell list_index={cell_index}"
                        )
                        print(
                            f"    row={actual_row}, "
                            f"col={actual_col}"
                        )
                        print(
                            f"    rowSpan={row_span}, "
                            f"colSpan={col_span}"
                        )
                        print(
                            f"    text={text}"
                        )

                table_index += 1

    print()
    print("=" * 100)
    print(f"총 Table 개수: {table_index}")
    print("=" * 100)


if __name__ == "__main__":
    main()