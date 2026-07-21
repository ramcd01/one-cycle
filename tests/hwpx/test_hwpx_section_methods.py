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

    print("HWPX 파일 로드 성공")

    sections = hwpx_file.sectionXMLFileList()

    section_count = sections.count()

    print()
    print("Section 목록 Class:", sections.getClass().getName())
    print("Section 개수:", section_count)

    if section_count == 0:
        print("Section이 없습니다.")
        return

    section = sections.get(0)

    print_methods(
        "[첫 번째 SectionXMLFile 메서드]",
        section
    )


if __name__ == "__main__":
    main()