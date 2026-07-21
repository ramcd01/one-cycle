import os
import jpype


JAR_PATH = r".\hwpxlib-1.0.8.jar"
HWPX_PATH = r".\(정정)고양창릉S-4블록공공분양입주자모집공고문.hwpx"


def start_jvm():
    if not jpype.isJVMStarted():
        jpype.startJVM(
            jpype.getDefaultJVMPath(),
            f"-Djava.class.path={os.path.abspath(JAR_PATH)}",
            convertStrings=True,
        )


def extract_text_from_t(t):
    try:
        if t.isOnlyText():
            text = t.onlyText()

            if text is not None:
                return str(text)

    except Exception:
        pass

    # isOnlyText()가 False인 경우에도
    # onlyText()가 일부 텍스트를 반환하는지 시도
    try:
        text = t.onlyText()

        if text is not None:
            return str(text)

    except Exception:
        pass

    return ""


def extract_cell_text(tc):
    sublist = tc.subList()

    if sublist is None:
        return ""

    texts = []

    for para_index in range(sublist.countOfPara()):
        para = sublist.getPara(para_index)

        para_texts = []

        for run_index in range(para.countOfRun()):
            run = para.getRun(run_index)

            for item_index in range(run.countOfRunItem()):
                item = run.getRunItem(item_index)

                if item is None:
                    continue

                class_name = item.getClass().getName()

                if class_name.endswith(".paragraph.T"):
                    text = extract_text_from_t(item)

                    if text:
                        para_texts.append(text)

        if para_texts:
            texts.append("".join(para_texts))

    return "\n".join(texts)


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
                        f"colCnt={table.colCnt()}, "
                        f"countOfTr={table.countOfTr()})"
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

                            text = extract_cell_text(tc)

                            print(
                                f"row={row}, "
                                f"col={col}, "
                                f"rowSpan={row_span}, "
                                f"colSpan={col_span}, "
                                f"text={text}"
                            )

                    table_index += 1

    print()
    print("=" * 100)
    print("총 Table 개수:", table_index)
    print("=" * 100)


if __name__ == "__main__":
    main()