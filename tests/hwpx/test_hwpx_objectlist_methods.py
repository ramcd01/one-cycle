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


def main():
    start_jvm()

    HWPXReader = jpype.JClass(
        "kr.dogfoot.hwpxlib.reader.HWPXReader"
    )

    hwpx_file = HWPXReader.fromFilepath(
        os.path.abspath(HWPX_PATH)
    )

    sections = hwpx_file.sectionXMLFileList()

    print("=" * 80)
    print("sectionXMLFileList 객체")
    print("=" * 80)

    print("Class:", sections.getClass().getName())

    print()
    print("[메서드 목록]")

    methods = sorted({
        method.getName()
        for method in sections.getClass().getMethods()
    })

    for method in methods:
        print(method)


if __name__ == "__main__":
    main()