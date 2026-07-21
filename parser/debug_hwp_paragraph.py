import argparse
import os

import jpype


def start_jvm(hwp_jar_path: str) -> None:
    if jpype.isJVMStarted():
        return

    jar_path = os.path.abspath(
        hwp_jar_path
    )

    if not os.path.exists(jar_path):
        raise FileNotFoundError(
            f"hwplib JAR 파일을 찾을 수 없습니다: {jar_path}"
        )

    jpype.startJVM(
        jpype.getDefaultJVMPath(),
        f"-Djava.class.path={jar_path}",
        convertStrings=True,
    )


def print_methods(obj, title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    methods = (
        obj
        .getClass()
        .getMethods()
    )

    method_names = sorted(
        {
            str(method.getName())
            for method in methods
        }
    )

    for method_name in method_names:
        print(method_name)


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

    file_path = os.path.abspath(
        args.file_path
    )

    HWPReader = jpype.JClass(
        "kr.dogfoot.hwplib.reader.HWPReader"
    )

    hwp_file = HWPReader.fromFile(
        file_path
    )

    body_text = (
        hwp_file
        .getBodyText()
    )

    sections = (
        body_text
        .getSectionList()
    )

    print(
        "Section 수:",
        len(sections),
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
        print(
            f"SECTION {section_index}"
        )

        print(
            "Paragraph 수:",
            len(paragraphs),
        )

        # 첫 번째 Paragraph의 API만 상세 출력
        if len(paragraphs) > 0:
            paragraph = paragraphs[0]

            print_methods(
                paragraph,
                "Paragraph Methods",
            )

            # Paragraph 내부 주요 객체 확인
            candidate_methods = [
                "getText",
                "getNormalString",
                "getParaText",
                "getControlList",
            ]

            print()
            print("=" * 100)
            print("Candidate Method Test")
            print("=" * 100)

            for method_name in candidate_methods:
                try:
                    method = getattr(
                        paragraph,
                        method_name,
                    )

                    result = method()

                    print()
                    print(
                        f"{method_name}()"
                    )

                    print(
                        "TYPE:",
                        (
                            result
                            .getClass()
                            .getName()
                            if (
                                result is not None
                                and hasattr(
                                    result,
                                    "getClass",
                                )
                            )
                            else type(result)
                        ),
                    )

                    print(
                        "VALUE:",
                        str(result)[:500],
                    )

                except Exception as exc:
                    print()
                    print(
                        f"{method_name}() ERROR:"
                    )

                    print(
                        exc
                    )

        # 너무 많이 출력하지 않도록
        # 첫 번째 Section만 검사
        break


if __name__ == "__main__":
    main()