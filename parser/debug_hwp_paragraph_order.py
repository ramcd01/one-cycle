import argparse
import os

import jpype


def start_jvm(hwp_jar_path: str) -> None:
    if jpype.isJVMStarted():
        return

    jar_path = os.path.abspath(
        hwp_jar_path
    )

    jpype.startJVM(
        jpype.getDefaultJVMPath(),
        f"-Djava.class.path={jar_path}",
        convertStrings=True,
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hwp_jar_path",
        required=True,
    )

    parser.add_argument(
        "--file_path",
        required=True,
    )

    args = parser.parse_args()

    start_jvm(
        args.hwp_jar_path
    )

    HWPReader = jpype.JClass(
        "kr.dogfoot.hwplib.reader.HWPReader"
    )

    file_path = os.path.abspath(
        args.file_path
    )

    hwp_file = HWPReader.fromFile(
        file_path
    )

    sections = (
        hwp_file
        .getBodyText()
        .getSectionList()
    )

    for section_index in range(
        len(sections)
    ):

        section = sections[
            section_index
        ]

        paragraphs = (
            section
            .getParagraphs()
        )

        print()
        print("=" * 100)

        print(
            f"SECTION {section_index}"
        )

        print(
            "Paragraph 수:",
            len(paragraphs)
        )

        print("=" * 100)

        for para_index in range(
            len(paragraphs)
        ):

            para = paragraphs[
                para_index
            ]

            print()
            print(
                "-" * 100
            )

            print(
                f"PARAGRAPH {para_index}"
            )

            # ------------------------------------------------
            # 일반 텍스트
            # ------------------------------------------------

            try:
                text = (
                    para
                    .getNormalString()
                )

                print(
                    "NORMAL STRING:"
                )

                print(
                    repr(
                        str(text)
                    )
                )

            except Exception as exc:

                print(
                    "getNormalString ERROR:",
                    exc
                )

            # ------------------------------------------------
            # Control
            # ------------------------------------------------

            try:
                controls = (
                    para
                    .getControlList()
                )

            except Exception:

                controls = None

            if controls is None:

                print(
                    "CONTROL COUNT: 0"
                )

                continue

            print(
                "CONTROL COUNT:",
                len(controls)
            )

            for control_index in range(
                len(controls)
            ):

                control = controls[
                    control_index
                ]

                class_name = (
                    control
                    .getClass()
                    .getName()
                )

                print()

                print(
                    f"CONTROL {control_index}"
                )

                print(
                    "CLASS:",
                    class_name
                )

                # --------------------------------------------
                # Paragraph 내 Control 위치 확인
                # --------------------------------------------

                try:
                    index = (
                        para
                        .getControlIndex(
                            control
                        )
                    )

                    print(
                        "CONTROL INDEX:",
                        index
                    )

                except Exception as exc:

                    print(
                        "CONTROL INDEX ERROR:",
                        exc
                    )

                # --------------------------------------------
                # Table 여부
                # --------------------------------------------

                if class_name.endswith(
                    ".ControlTable"
                ):

                    print(
                        "TYPE: TABLE"
                    )


if __name__ == "__main__":
    main()