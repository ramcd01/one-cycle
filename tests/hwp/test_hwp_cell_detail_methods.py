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


def print_methods(title, obj):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    if obj is None:
        print("객체가 None입니다.")
        return

    print("Class:", obj.getClass().getName())

    methods = sorted({
        method.getName()
        for method in obj.getClass().getMethods()
    })

    for method in methods:
        print(method)


def main():
    start_jvm()

    HWPReader = jpype.JPackage(
        "kr.dogfoot.hwplib.reader"
    ).HWPReader

    hwp_file = HWPReader.fromFile(
        os.path.abspath(HWP_PATH)
    )

    sections = hwp_file.getBodyText().getSectionList()

    for section_index in range(sections.size()):
        section = sections.get(section_index)
        paragraphs = section.getParagraphs()

        for paragraph_index in range(len(paragraphs)):
            paragraph = paragraphs[paragraph_index]

            try:
                controls = paragraph.getControlList()
            except Exception:
                try:
                    controls = paragraph.getControls()
                except Exception:
                    continue

            if controls is None:
                continue

            try:
                control_count = controls.size()
                get_control = controls.get
            except AttributeError:
                control_count = len(controls)
                get_control = lambda i: controls[i]

            for control_index in range(control_count):
                control = get_control(control_index)

                if not control.getClass().getName().endswith(
                    "ControlTable"
                ):
                    continue

                rows = control.getRowList()

                if rows.size() == 0:
                    continue

                cells = rows.get(0).getCellList()

                if cells.size() == 0:
                    continue

                cell = cells.get(0)

                print("첫 번째 셀 발견")
                print("Section:", section_index)
                print("Paragraph:", paragraph_index)

                # 1. 셀 구조/병합 관련 객체
                list_header = cell.getListHeader()

                print_methods(
                    "[ListHeader 메서드]",
                    list_header
                )

                # 2. 셀 내부 텍스트 관련 객체
                paragraph_list = cell.getParagraphList()

                print_methods(
                    "[ParagraphList 메서드]",
                    paragraph_list
                )

                return


if __name__ == "__main__":
    main()