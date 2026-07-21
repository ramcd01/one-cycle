import os
import jpype


JAR_PATH = r".\hwplib-1.1.8.jar"
HWP_PATH = r".\★청년매입임대주택_서류제출안내문(26년2차).hwp"


def start_jvm():
    if not jpype.isJVMStarted():
        jpype.startJVM(
            jpype.getDefaultJVMPath(),
            f"-Djava.class.path={os.path.abspath(JAR_PATH)}",
            convertStrings=True,
        )


def get_collection_size(collection):
    """
    Java List 또는 Java Array 모두 대응
    """
    if collection is None:
        return 0

    try:
        return collection.size()
    except AttributeError:
        return len(collection)


def get_collection_item(collection, index):
    """
    Java List 또는 Java Array 모두 대응
    """
    try:
        return collection.get(index)
    except AttributeError:
        return collection[index]


def get_method_names(obj):
    """
    Java 객체가 제공하는 메서드명 확인
    """
    return {
        method.getName()
        for method in obj.getClass().getMethods()
    }


def safe_call(obj, method_names, default=None):
    """
    여러 후보 메서드 중 실제 존재하는 메서드를 호출
    """
    methods = get_method_names(obj)

    for method_name in method_names:
        if method_name in methods:
            try:
                return getattr(obj, method_name)()
            except Exception:
                pass

    return default


def extract_paragraph_text(paragraph):
    """
    Paragraph 객체 내부의 텍스트를 최대한 간단하게 확인.
    우선 ParaText 객체 접근을 시도한다.
    """
    if paragraph is None:
        return ""

    methods = get_method_names(paragraph)

    if "getText" not in methods:
        return ""

    try:
        para_text = paragraph.getText()
    except Exception:
        return ""

    if para_text is None:
        return ""

    # ParaText 자체를 str()로 변환했을 때 의미 없는 객체명이
    # 나올 수 있으므로 실제 메서드 탐색
    para_text_methods = get_method_names(para_text)

    # 버전에 따라 getNormalString 등이 존재할 가능성 확인
    candidates = [
        "getNormalString",
        "getText",
        "toString",
    ]

    for method_name in candidates:
        if method_name in para_text_methods:
            try:
                value = getattr(para_text, method_name)()

                if value is not None:
                    text = str(value)

                    # Java 객체 식별자 같은 값은 제외
                    if "@" not in text:
                        return text

            except Exception:
                pass

    return ""


def inspect_cell(cell, row_index, cell_index):
    """
    셀의 위치/병합 관련 속성을 확인
    """

    print(
        f"      Cell {cell_index}"
    )

    print(
        "        Class:",
        cell.getClass().getName()
    )

    methods = get_method_names(cell)

    # 셀이 실제로 제공하는 위치/병합 관련 메서드 후보
    property_candidates = {
        "row_address": [
            "getRowAddress",
            "getRowIndex",
        ],
        "col_address": [
            "getColumnAddress",
            "getColAddress",
            "getColumnIndex",
        ],
        "row_span": [
            "getRowSpan",
        ],
        "col_span": [
            "getColumnSpan",
            "getColSpan",
        ],
    }

    for label, candidates in property_candidates.items():

        value = None

        for method_name in candidates:
            if method_name in methods:
                try:
                    value = getattr(
                        cell,
                        method_name
                    )()

                    break

                except Exception:
                    pass

        print(
            f"        {label}: {value}"
        )

    # Cell 내부 ParagraphList 확인
    paragraph_list = None

    if "getParagraphList" in methods:
        try:
            paragraph_list = (
                cell.getParagraphList()
            )
        except Exception:
            pass

    if paragraph_list is None:
        print(
            "        text: "
            "[ParagraphList 접근 실패]"
        )
        return

    paragraph_methods = get_method_names(
        paragraph_list
    )

    paragraphs = None

    if "getParagraphs" in paragraph_methods:
        try:
            paragraphs = (
                paragraph_list.getParagraphs()
            )
        except Exception:
            pass

    if paragraphs is None:
        print(
            "        text: "
            "[Paragraph 접근 실패]"
        )
        return

    texts = []

    paragraph_count = (
        get_collection_size(paragraphs)
    )

    for i in range(paragraph_count):

        paragraph = (
            get_collection_item(
                paragraphs,
                i
            )
        )

        text = extract_paragraph_text(
            paragraph
        )

        if text:
            texts.append(text)

    print(
        "        text:",
        " | ".join(texts)
        if texts
        else "[텍스트 추출 실패]"
    )


def inspect_table(
    table,
    section_index,
    paragraph_index,
    table_index,
):

    print()
    print("=" * 80)

    print(
        f"[TABLE {table_index}] "
        f"Section={section_index}, "
        f"Paragraph={paragraph_index}"
    )

    print("=" * 80)

    methods = get_method_names(table)

    print(
        "Table Class:",
        table.getClass().getName()
    )

    # ControlTable의 행 목록
    if "getRowList" not in methods:

        print(
            "getRowList() 메서드가 없습니다."
        )

        print(
            "사용 가능한 메서드:"
        )

        for name in sorted(methods):
            print(
                " ",
                name
            )

        return

    rows = table.getRowList()

    row_count = get_collection_size(
        rows
    )

    print(
        f"Row 개수: {row_count}"
    )

    for row_index in range(
        row_count
    ):

        row = get_collection_item(
            rows,
            row_index
        )

        print()
        print(
            f"  [ROW {row_index}]"
        )

        row_methods = get_method_names(
            row
        )

        if "getCellList" not in row_methods:

            print(
                "    getCellList() 없음"
            )

            continue

        cells = row.getCellList()

        cell_count = (
            get_collection_size(
                cells
            )
        )

        print(
            f"    Cell 개수: "
            f"{cell_count}"
        )

        for cell_index in range(
            cell_count
        ):

            cell = (
                get_collection_item(
                    cells,
                    cell_index
                )
            )

            inspect_cell(
                cell,
                row_index,
                cell_index,
            )


def main():

    start_jvm()

    HWPReader = jpype.JPackage(
        "kr.dogfoot.hwplib.reader"
    ).HWPReader

    hwp_file = HWPReader.fromFile(
        os.path.abspath(
            HWP_PATH
        )
    )

    body_text = (
        hwp_file.getBodyText()
    )

    sections = (
        body_text.getSectionList()
    )

    total_tables = 0

    section_count = (
        get_collection_size(
            sections
        )
    )

    for section_index in range(
        section_count
    ):

        section = (
            get_collection_item(
                sections,
                section_index
            )
        )

        paragraphs = (
            section.getParagraphs()
        )

        paragraph_count = (
            get_collection_size(
                paragraphs
            )
        )

        for paragraph_index in range(
            paragraph_count
        ):

            paragraph = (
                get_collection_item(
                    paragraphs,
                    paragraph_index
                )
            )

            methods = (
                get_method_names(
                    paragraph
                )
            )

            controls = None

            if "getControlList" in methods:

                controls = (
                    paragraph
                    .getControlList()
                )

            elif "getControls" in methods:

                controls = (
                    paragraph
                    .getControls()
                )

            if controls is None:
                continue

            control_count = (
                get_collection_size(
                    controls
                )
            )

            for control_index in range(
                control_count
            ):

                control = (
                    get_collection_item(
                        controls,
                        control_index
                    )
                )

                class_name = (
                    control
                    .getClass()
                    .getName()
                )

                if class_name.endswith(
                    "ControlTable"
                ):

                    inspect_table(
                        control,
                        section_index,
                        paragraph_index,
                        total_tables,
                    )

                    total_tables += 1

    print()
    print("=" * 80)

    print(
        f"총 Table 개수: "
        f"{total_tables}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()