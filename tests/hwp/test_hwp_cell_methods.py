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

                class_name = control.getClass().getName()

                if not class_name.endswith("ControlTable"):
                    continue

                rows = control.getRowList()

                if rows.size() == 0:
                    continue

                row = rows.get(0)
                cells = row.getCellList()

                if cells.size() == 0:
                    continue

                cell = cells.get(0)

                print("=" * 80)
                print("첫 번째 Table / Row / Cell 발견")
                print("=" * 80)

                print("Section:", section_index)
                print("Paragraph:", paragraph_index)
                print("Cell Class:", cell.getClass().getName())

                print()
                print("[Cell 메서드 목록]")
                print("-" * 80)

                methods = sorted({
                    method.getName()
                    for method in cell.getClass().getMethods()
                })

                for method in methods:
                    print(method)

                return

    print("Cell을 찾지 못했습니다.")


if __name__ == "__main__":
    main()