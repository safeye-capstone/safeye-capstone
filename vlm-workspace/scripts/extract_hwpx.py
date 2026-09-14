from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


# 프로젝트 최상위 경로
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_LAWS_DIR = BASE_DIR / "data" / "raw_laws"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def local_name(tag: str) -> str:
    """
    XML 태그에서 namespace를 제거한다.

    예:
    {http://www.hancom.co.kr/hwpml/2011/paragraph}t
    -> t
    """
    return tag.split("}")[-1]


def extract_paragraphs_from_xml(xml_data: bytes) -> list[str]:
    """
    HWPX section XML에서 문단별 텍스트를 추출한다.
    """

    root = ET.fromstring(xml_data)
    paragraphs = []

    for element in root.iter():
        # HWPX에서 p 태그가 문단 역할
        if local_name(element.tag) != "p":
            continue

        texts = []

        for child in element.iter():
            # 실제 문자 데이터는 주로 t 태그 안에 존재
            if local_name(child.tag) == "t" and child.text:
                text = child.text.strip()

                if text:
                    texts.append(text)

        paragraph = "".join(texts).strip()

        if paragraph:
            paragraphs.append(paragraph)

    return paragraphs


def extract_hwpx(hwpx_path: Path) -> str:
    """
    HWPX 파일 하나의 전체 텍스트를 추출한다.
    """

    all_paragraphs = []

    with zipfile.ZipFile(hwpx_path, "r") as hwpx:
        # 본문 section XML 찾기
        section_files = [
            name
            for name in hwpx.namelist()
            if name.startswith("Contents/section")
            and name.endswith(".xml")
        ]

        # section0, section1 ... 순서 보장
        section_files.sort()

        for section_file in section_files:
            xml_data = hwpx.read(section_file)
            paragraphs = extract_paragraphs_from_xml(xml_data)
            all_paragraphs.extend(paragraphs)

    return "\n".join(all_paragraphs)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    hwpx_files = list(RAW_LAWS_DIR.glob("*.hwpx"))

    if not hwpx_files:
        print(f"HWPX 파일을 찾을 수 없습니다: {RAW_LAWS_DIR}")
        return

    print(f"{len(hwpx_files)}개의 HWPX 파일을 발견했습니다.")

    for hwpx_path in hwpx_files:
        print(f"\n처리 중: {hwpx_path.name}")

        try:
            text = extract_hwpx(hwpx_path)

            output_path = PROCESSED_DIR / f"{hwpx_path.stem}.txt"

            output_path.write_text(
                text,
                encoding="utf-8",
            )

            print(f"완료 → {output_path}")

        except Exception as error:
            print(f"실패: {hwpx_path.name}")
            print(error)


if __name__ == "__main__":
    main()