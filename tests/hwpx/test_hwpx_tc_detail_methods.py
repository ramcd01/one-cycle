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
    print("=" * 100)
    print(title)
    print("=" * 100)

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

            for run_index in range(para.countOfRun()):
                run = para.getRun(run_index)

                for item_index in range(run.countOfRunItem()):
                    item = run.getRunItem(item_index)

                    if item is None:
                        continue

                    if not item.getClass().getName().endswith(".Table"):
                        continue

                    table = item

                    for tr_index in range(table.countOfTr()):
                        tr = table.getTr(tr_index)

                        if tr.countOfTc() == 0:
                            continue

                        tc = tr.getTc(0)

                        print(
                            f"Cell 위치: "
                            f"Section={section_index}, "
                            f"Para={para_index}, "
                            f"Run={run_index}, "
                            f"Item={item_index}, "
                            f"Tr={tr_index}, "
                            f"Tc=0"
                        )

                        print_methods(
                            "[cellAddr 객체 메서드]",
                            tc.cellAddr()
                        )

                        print_methods(
                            "[cellSpan 객체 메서드]",
                            tc.cellSpan()
                        )

                        print_methods(
                            "[subList 객체 메서드]",
                            tc.subList()
                        )

                        return


if __name__ == "__main__":
    main()