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


def extract_text_from_sublist(sublist):
    texts = []

    for para_index in range(sublist.countOfPara()):
        para = sublist.getPara(para_index)

        for run_index in range(para.countOfRun()):
            run = para.getRun(run_index)

            for item_index in range(run.countOfRunItem()):
                item = run.getRunItem(item_index)

                if item is None:
                    continue

                class_name = item.getClass().getName()

                print(
                    "    RunItem:",
                    class_name
                )

    return " ".join(texts)


def main():
    start_jvm()

    HWPXReader = jpype.JClass(
        "kr.dogfoot.hwpxlib.reader.HWPXReader"
    )

    hwpx_file = HWPXReader.fromFilepath(
        os.path.abspath(HWPX_PATH)
    )

    sections = hwpx_file.sectionXMLFileList()

    table_index = 0

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

                    print()
                    print("=" * 100)
                    print(
                        f"TABLE {table_index} "
                        f"(rowCnt={table.rowCnt()}, "
                        f"colCnt={table.colCnt()})"
                    )
                    print("=" * 100)

                    for tr_index in range(table.countOfTr()):
                        tr = table.getTr(tr_index)

                        for tc_index in range(tr.countOfTc()):
                            tc = tr.getTc(tc_index)

                            addr = tc.cellAddr()
                            span = tc.cellSpan()

                            row = addr.rowAddr()
                            col = addr.colAddr()
                            row_span = span.rowSpan()
                            col_span = span.colSpan()

                            print()
                            print(
                                f"Cell "
                                f"row={row}, "
                                f"col={col}, "
                                f"rowSpan={row_span}, "
                                f"colSpan={col_span}"
                            )

                            sublist = tc.subList()

                            if sublist is not None:
                                extract_text_from_sublist(
                                    sublist
                                )

                    table_index += 1

                    # 우선 첫 번째 표만 확인
                    return


if __name__ == "__main__":
    main()