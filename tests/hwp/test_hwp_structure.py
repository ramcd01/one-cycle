import jpype
import os

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

    print("=" * 80)
    print("HWP 구조 탐색 시작")
    print("=" * 80)

    body_text = hwp_file.getBodyText()
    section_list = body_text.getSectionList()

    print(f"Section 개수: {section_list.size()}")

    for section_index in range(section_list.size()):
        section = section_list.get(section_index)

        print("=" * 80)
        print(f"[SECTION {section_index}]")
        print("=" * 80)

        # Paragraph[] Java 배열
        paragraphs = section.getParagraphs()

        print(f"Paragraph 개수: {len(paragraphs)}")

        for paragraph_index in range(len(paragraphs)):
            paragraph = paragraphs[paragraph_index]

            print(f"\n--- Paragraph {paragraph_index} ---")
            print(
                "Class:",
                paragraph.getClass().getName(),
            )

            # Paragraph가 제공하는 메서드 확인
            methods = {
                method.getName()
                for method in paragraph.getClass().getMethods()
            }

            if "getControlList" in methods:
                controls = paragraph.getControlList()
            elif "getControls" in methods:
                controls = paragraph.getControls()
            else:
                print("Control 접근 메서드 없음")
                continue

            if controls is None:
                print("Controls: 없음")
                continue

            # controls가 Java List인지 배열인지 모두 처리
            try:
                control_count = controls.size()
                print(f"Controls: {control_count}개")

                for control_index in range(control_count):
                    control = controls.get(control_index)

                    print(
                        f"  Control {control_index}: "
                        f"{control.getClass().getName()}"
                    )

            except AttributeError:
                control_count = len(controls)
                print(f"Controls: {control_count}개")

                for control_index in range(control_count):
                    control = controls[control_index]

                    print(
                        f"  Control {control_index}: "
                        f"{control.getClass().getName()}"
                    )


if __name__ == "__main__":
    main()