import os
import jpype
from collections import Counter


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

    type_counter = Counter()
    first_locations = {}

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

                    class_name = item.getClass().getName()

                    type_counter[class_name] += 1

                    if class_name not in first_locations:
                        first_locations[class_name] = (
                            section_index,
                            para_index,
                            run_index,
                            item_index
                        )

    print("=" * 100)
    print("[RunItem 클래스 종류]")
    print("=" * 100)

    for class_name, count in type_counter.most_common():
        location = first_locations[class_name]

        print()
        print("Class:", class_name)
        print("Count:", count)
        print(
            "First Location:",
            f"Section={location[0]}, "
            f"Para={location[1]}, "
            f"Run={location[2]}, "
            f"Item={location[3]}"
        )


if __name__ == "__main__":
    main()