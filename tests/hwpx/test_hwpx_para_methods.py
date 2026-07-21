import os
import jpype


JAR_PATH = r".\hwpxlib-1.0.8.jar"
HWPX_PATH = r".\★청년매입임대주택_서류제출안내문(26년2차).hwpx"


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

    HWPXReader = jpype.JClass(
        "kr.dogfoot.hwpxlib.reader.HWPXReader"
    )

    hwpx_file = HWPXReader.fromFilepath(
        os.path.abspath(HWPX_PATH)
    )

    sections = hwpx_file.sectionXMLFileList()

    print("Section 개수:", sections.count())

    for section_index in range(sections.count()):
        section = sections.get(section_index)

        para_count = section.countOfPara()

        print()
        print(
            f"Section {section_index} Paragraph 개수:",
            para_count
        )

        if para_count > 0:
            para = section.getPara(0)

            print_methods(
                f"[Section {section_index} 첫 번째 Paragraph 메서드]",
                para
            )

            break


if __name__ == "__main__":
    main()