import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


TARGET_CODEPOINT = 0xF02D6


def local_name(name: str) -> str:
    if "}" in name:
        return name.split("}", 1)[1]
    return name


def get_attributes(
    element: ET.Element,
) -> dict[str, str]:
    return {
        local_name(key): value
        for key, value in element.attrib.items()
    }


def find_section_xml_files(
    zip_file: zipfile.ZipFile,
) -> list[str]:
    """
    HWPX ZIP 내부 section*.xml 파일 목록 검색
    """
    result = []

    for name in zip_file.namelist():

        filename = (
            Path(name)
            .name
            .lower()
        )

        if (
            filename.startswith("section")
            and filename.endswith(".xml")
        ):
            result.append(name)

    return sorted(result)


def build_parent_map(
    root: ET.Element,
) -> dict[ET.Element, ET.Element]:
    return {
        child: parent
        for parent in root.iter()
        for child in parent
    }


def contains_target_char(
    text: str | None,
) -> bool:
    if not text:
        return False

    return any(
        ord(char) == TARGET_CODEPOINT
        for char in text
    )


def find_target_elements(
    root: ET.Element,
) -> list[ET.Element]:
    """
    자신의 text 또는 tail에 대상 PUA 문자를 포함한 Element 검색
    """
    result = []

    for element in root.iter():

        if contains_target_char(
            element.text
        ):
            result.append(
                element
            )
            continue

        if contains_target_char(
            element.tail
        ):
            result.append(
                element
            )

    return result


def find_nearest_ancestor(
    element: ET.Element,
    parent_map: dict[
        ET.Element,
        ET.Element,
    ],
    target_tag: str,
) -> ET.Element | None:

    current = element

    while current in parent_map:

        current = (
            parent_map[
                current
            ]
        )

        if (
            local_name(
                current.tag
            )
            == target_tag
        ):
            return current

    return None


def element_to_string(
    element: ET.Element,
) -> str:
    """
    XML Element를 문자열로 변환
    """
    return ET.tostring(
        element,
        encoding="unicode",
    )


def print_element_summary(
    title: str,
    element: ET.Element | None,
) -> None:

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    if element is None:
        print("해당 Element를 찾지 못했습니다.")
        return

    print(
        f"tag: "
        f"{local_name(element.tag)}"
    )

    attrs = (
        get_attributes(
            element
        )
    )

    if attrs:

        print()
        print("[속성]")

        for key, value in (
            attrs.items()
        ):

            print(
                f"- {key}: "
                f"{value}"
            )

    print()
    print("[XML]")
    print(
        element_to_string(
            element
        )
    )


def inspect_section_xml(
    section_path: str,
    xml_data: bytes,
) -> int:

    root = ET.fromstring(
        xml_data
    )

    parent_map = (
        build_parent_map(
            root
        )
    )

    matched_elements = (
        find_target_elements(
            root
        )
    )

    if not matched_elements:
        return 0

    print()
    print("#" * 80)
    print(
        f"대상 문자 발견: "
        f"{section_path}"
    )
    print("#" * 80)

    print(
        f"발견 Element 수: "
        f"{len(matched_elements)}"
    )

    for index, element in enumerate(
        matched_elements
    ):

        print()
        print(
            "*" * 80
        )

        print(
            f"[발견 위치 {index}]"
        )

        print(
            "*" * 80
        )

        print(
            f"현재 Element tag: "
            f"{local_name(element.tag)}"
        )

        print(
            f"현재 Element text: "
            f"{element.text!r}"
        )

        print(
            f"현재 Element tail: "
            f"{element.tail!r}"
        )

        # ----------------------------------------------------
        # 가장 가까운 t
        # ----------------------------------------------------
        if (
            local_name(
                element.tag
            )
            == "t"
        ):
            t_element = element

        else:
            t_element = (
                find_nearest_ancestor(
                    element,
                    parent_map,
                    "t",
                )
            )

        # ----------------------------------------------------
        # 가장 가까운 run
        # ----------------------------------------------------
        if (
            local_name(
                element.tag
            )
            == "run"
        ):
            run_element = element

        else:
            run_element = (
                find_nearest_ancestor(
                    element,
                    parent_map,
                    "run",
                )
            )

        # ----------------------------------------------------
        # 가장 가까운 para
        # ----------------------------------------------------
        para_element = (
            find_nearest_ancestor(
                element,
                parent_map,
                "p",
            )
        )

        print_element_summary(
            "가장 가까운 <t>",
            t_element,
        )

        print_element_summary(
            "가장 가까운 <run>",
            run_element,
        )

        print_element_summary(
            "가장 가까운 <p>",
            para_element,
        )

        # ----------------------------------------------------
        # 부모 체인 출력
        # ----------------------------------------------------
        print()
        print("=" * 80)
        print(
            "부모 체인"
        )
        print("=" * 80)

        chain = []

        current = element

        while current in parent_map:

            current = (
                parent_map[
                    current
                ]
            )

            chain.append(
                local_name(
                    current.tag
                )
            )

        print(
            " -> ".join(
                chain
            )
        )

    return len(
        matched_elements
    )


def inspect_hwpx(
    hwpx_file_path: str,
) -> None:

    print()
    print("=" * 80)
    print(
        "HWPX section.xml PUA 문맥 추적"
    )
    print("=" * 80)

    print(
        f"파일: "
        f"{hwpx_file_path}"
    )

    print(
        f"대상 코드포인트: "
        f"U+{TARGET_CODEPOINT:05X}"
    )

    total_found = 0

    with zipfile.ZipFile(
        hwpx_file_path,
        "r",
    ) as zf:

        section_files = (
            find_section_xml_files(
                zf
            )
        )

        print()
        print(
            f"section XML 수: "
            f"{len(section_files)}"
        )

        for section_path in (
            section_files
        ):

            print(
                f"- {section_path}"
            )

        for section_path in (
            section_files
        ):

            xml_data = (
                zf.read(
                    section_path
                )
            )

            total_found += (
                inspect_section_xml(
                    section_path,
                    xml_data,
                )
            )

    print()
    print("=" * 80)

    print(
        f"전체 발견 횟수: "
        f"{total_found}"
    )

    print("=" * 80)


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "HWPX section.xml에서 "
            "PUA 문자의 실제 XML 문맥을 추적합니다."
        )
    )

    parser.add_argument(
        "--file_path",
        required=True,
        help=(
            "검사할 HWPX 파일 경로"
        ),
    )

    args = (
        parser.parse_args()
    )

    inspect_hwpx(
        args.file_path
    )


if __name__ == "__main__":
    main()