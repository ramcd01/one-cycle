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

                        for tc_index in range(tr.countOfTc()):
                            tc = tr.getTc(tc_index)

                            sublist = tc.subList()

                            if sublist is None:
                                continue

                            for sub_para_index in range(
                                sublist.countOfPara()
                            ):
                                sub_para = sublist.getPara(
                                    sub_para_index
                                )

                                for sub_run_index in range(
                                    sub_para.countOfRun()
                                ):
                                    sub_run = sub_para.getRun(
                                        sub_run_index
                                    )

                                    for sub_item_index in range(
                                        sub_run.countOfRunItem()
                                    ):
                                        sub_item = sub_run.getRunItem(
                                            sub_item_index
                                        )

                                        if sub_item is None:
                                            continue

                                        class_name = (
                                            sub_item
                                            .getClass()
                                            .getName()
                                        )

                                        if class_name.endswith(
                                            ".paragraph.T"
                                        ):
                                            print_methods(
                                                "[T 객체 메서드]",
                                                sub_item
                                            )
                                            return


if __name__ == "__main__":
    main()