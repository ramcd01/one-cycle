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

    for section_index in range(sections.count()):
        section = sections.get(section_index)

        for para_index in range(section.countOfPara()):
            para = section.getPara(para_index)

            run_count = para.countOfRun()

            if run_count > 0:
                print(
                    f"Section {section_index}, "
                    f"Paragraph {para_index}, "
                    f"Run 개수: {run_count}"
                )

                run = para.getRun(0)

                print_methods(
                    "[첫 번째 Run 객체 메서드]",
                    run
                )

                return


if __name__ == "__main__":
    main()