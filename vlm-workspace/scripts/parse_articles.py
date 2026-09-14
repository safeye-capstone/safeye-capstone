from pathlib import Path
import json
import re


# ============================================================
# 프로젝트 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PARSED_DIR = BASE_DIR / "data" / "parsed"
OUTPUT_PATH = PARSED_DIR / "regulations.jsonl"


# ============================================================
# 별표 Chunk 설정
# ============================================================

# 별표는 일반 조문 구조가 아니므로
# 일정 길이의 문단 묶음으로 나눈다.
ANNEX_MAX_CHARS = 1500

# 다음 chunk에 이전 문단 1개를 겹쳐서
# 문맥 단절을 줄인다.
ANNEX_OVERLAP_PARAGRAPHS = 1


# ============================================================
# 일반 조문 Pattern
#
# 제42조(...)
# 제42조의2(...)
# ============================================================

ARTICLE_PATTERN = re.compile(
    r"^("
    r"제\s*\d+\s*조"
    r"(?:의\s*\d+)?"
    r"(?:\([^)]*\))?"
    r")"
)


# ============================================================
# 별표 번호 Pattern
#
# 별표1
# 별표 1
# 별표_1
# ============================================================

ANNEX_NUMBER_PATTERN = re.compile(
    r"별표[\s_\-]*(\d+)",
    re.IGNORECASE,
)


# ============================================================
# 문자열 정리
# ============================================================

def normalize_spaces(text: str) -> str:
    """지나치게 많은 공백과 탭을 정리한다."""

    return re.sub(r"[ \t]+", " ", text).strip()


# ============================================================
# 정식 법령 이름 생성
# ============================================================

def get_law_name(filename_stem: str) -> str:
    """
    파일명 대신 RAG metadata에 사용할
    법령명을 정리한다.
    """

    if "중대재해처벌법" in filename_stem:
        if "시행령" in filename_stem:
            return "중대재해 처벌 등에 관한 법률 시행령"

        return "중대재해 처벌 등에 관한 법률"

    return filename_stem


# ============================================================
# 문서 종류 판정
# ============================================================

def guess_document_type(filename_stem: str) -> str:
    """
    산업안전보건법 계열과
    중대재해처벌법 계열을 구분한다.
    """

    # --------------------------------------------------------
    # 중대재해처벌법 계열
    # --------------------------------------------------------

    if "중대재해처벌법" in filename_stem:
        if "시행령" in filename_stem and "별표" in filename_stem:
            return "SERIOUS_ACCIDENT_DECREE_ANNEX"

        if "시행령" in filename_stem:
            return "SERIOUS_ACCIDENT_DECREE"

        return "SERIOUS_ACCIDENT_LAW"

    # --------------------------------------------------------
    # 기존 산업안전보건법 계열
    # --------------------------------------------------------

    if "기준에 관한 규칙" in filename_stem:
        return "SAFETY_REGULATION"

    if "시행규칙" in filename_stem:
        return "ENFORCEMENT_RULE"

    if "시행령" in filename_stem:
        return "ENFORCEMENT_DECREE"

    return "LAW"


# ============================================================
# 별표 파일인지 확인
# ============================================================

def is_annex_file(txt_path: Path) -> bool:
    return "별표" in txt_path.stem


# ============================================================
# 조문 제목 해석
# ============================================================

def parse_article_header(header: str) -> tuple[str, str]:
    """
    제42조(추락의 방지)

    ->
    article = 제42조
    title = 추락의 방지
    """

    article_match = re.search(
        r"제\s*\d+\s*조"
        r"(?:의\s*\d+)?",
        header,
    )
    title_match = re.search(r"\((.*?)\)", header)

    article = article_match.group(0) if article_match else header

    # 제 42 조 → 제42조
    article = re.sub(r"\s+", "", article)

    title = title_match.group(1).strip() if title_match else ""

    return article, title


# ============================================================
# 일반 법령 조문 분할
# ============================================================

def split_articles(text: str) -> list[dict]:
    """일반 법령 TXT를 제○조 단위로 분리한다."""

    lines = text.splitlines()
    articles = []

    current_header = None
    current_content = []

    for raw_line in lines:
        line = normalize_spaces(raw_line)

        if not line:
            continue

        # 새로운 제○조가 시작됨
        if ARTICLE_PATTERN.match(line):
            # 이전 조문 저장
            if current_header:
                articles.append(
                    {
                        "header": current_header,
                        "content": "\n".join(current_content).strip(),
                    }
                )

            current_header = line
            current_content = []

        elif current_header:
            current_content.append(line)

    # 마지막 조문 저장
    if current_header:
        articles.append(
            {
                "header": current_header,
                "content": "\n".join(current_content).strip(),
            }
        )

    return articles


# ============================================================
# 별표 번호
# ============================================================

def get_annex_number(filename_stem: str) -> str:
    """
    중대재해처벌법_시행령_별표4
    ->
    별표 4
    """

    match = ANNEX_NUMBER_PATTERN.search(filename_stem)

    if not match:
        return "별표"

    return f"별표 {match.group(1)}"


# ============================================================
# 별표 제목 추출
# ============================================================

def get_annex_title(text: str, annex_no: str) -> str:
    """
    별표 파일 시작 부분에서
    사람이 읽을 수 있는 제목을 찾아본다.

    찾기 어려우면 별표 번호를 사용한다.
    """

    lines = [
        normalize_spaces(line)
        for line in text.splitlines()
        if normalize_spaces(line)
    ]

    for line in lines[:10]:
        # [별표 4] 같은 줄은 제목 후보에서 제외
        if "별표" in line and len(line) <= 30:
            continue

        # 너무 긴 본문 문장은 제목으로 사용하지 않음
        if len(line) <= 120:
            return line

    return annex_no


# ============================================================
# 별표 Chunking
# ============================================================

def split_annex_chunks(text: str) -> list[str]:
    """
    별표는 제○조 구조가 아니므로
    문단 기반으로 약 1500자씩 분할한다.

    표가 TXT로 풀렸더라도
    원래 문단 순서는 최대한 보존한다.
    """

    paragraphs = [
        normalize_spaces(line)
        for line in text.splitlines()
        if normalize_spaces(line)
    ]

    if not paragraphs:
        return []

    chunks = []
    current = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph) + 1

        # 현재 chunk가 이미 있고,
        # 새 문단을 넣으면 한도를 넘는 경우
        if (
            current
            and current_length + paragraph_length > ANNEX_MAX_CHARS
        ):
            chunks.append("\n".join(current).strip())

            # 마지막 문단 일부를 다음 chunk에 중복
            # → 문맥이 끊기는 것을 완화
            if ANNEX_OVERLAP_PARAGRAPHS > 0:
                current = current[-ANNEX_OVERLAP_PARAGRAPHS:]
                current_length = sum(len(item) + 1 for item in current)
            else:
                current = []
                current_length = 0

        current.append(paragraph)
        current_length += paragraph_length

    # 마지막 chunk
    if current:
        chunks.append("\n".join(current).strip())

    return chunks


# ============================================================
# 일반 법령 처리
# ============================================================

def process_article_file(txt_path: Path) -> list[dict]:
    filename_stem = txt_path.stem
    law_name = get_law_name(filename_stem)
    document_type = guess_document_type(filename_stem)
    text = txt_path.read_text(encoding="utf-8")
    articles = split_articles(text)

    records = []

    for index, item in enumerate(articles, start=1):
        article, title = parse_article_header(item["header"])

        content = (
            f"{item['header']}\n"
            f"{item['content']}"
        ).strip()

        records.append(
            {
                "chunk_id": f"{filename_stem}-{index:04d}",
                "law_name": law_name,
                "document_type": document_type,
                "article": article,
                "article_title": title,
                "annex_no": "",
                "annex_title": "",
                "source": "국가법령정보센터",
                "content": content,
            }
        )

    return records


# ============================================================
# 별표 처리
# ============================================================

def process_annex_file(txt_path: Path) -> list[dict]:
    filename_stem = txt_path.stem
    law_name = get_law_name(filename_stem)
    document_type = guess_document_type(filename_stem)
    text = txt_path.read_text(encoding="utf-8")

    annex_no = get_annex_number(filename_stem)
    annex_title = get_annex_title(text, annex_no)
    chunks = split_annex_chunks(text)

    records = []

    for index, content in enumerate(chunks, start=1):
        records.append(
            {
                "chunk_id": f"{filename_stem}-annex-{index:04d}",
                "law_name": law_name,
                "document_type": document_type,
                "article": "",
                "article_title": "",
                "annex_no": annex_no,
                "annex_title": annex_title,
                "source": "국가법령정보센터",
                "content": content,
            }
        )

    return records


# ============================================================
# 파일 처리
# ============================================================

def process_file(txt_path: Path) -> list[dict]:
    if is_annex_file(txt_path):
        return process_annex_file(txt_path)

    return process_article_file(txt_path)


# ============================================================
# Main
# ============================================================

def main() -> None:
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(
        PROCESSED_DIR.glob("*.txt"),
        key=lambda path: path.name,
    )

    if not txt_files:
        print("processed 폴더에 TXT 파일이 없습니다.")
        return

    total_records = []
    article_count = 0
    annex_chunk_count = 0

    for txt_path in txt_files:
        print()

        # ----------------------------------------------------
        # 별표
        # ----------------------------------------------------

        if is_annex_file(txt_path):
            print(f"별표 분석 중: {txt_path.name}")

            records = process_annex_file(txt_path)

            print(f"  → {len(records)}개 별표 chunk")
            annex_chunk_count += len(records)

        # ----------------------------------------------------
        # 일반 법령
        # ----------------------------------------------------

        else:
            print(f"조문 분석 중: {txt_path.name}")

            records = process_article_file(txt_path)

            print(f"  → {len(records)}개 조문")
            article_count += len(records)

        total_records.extend(records)

    # --------------------------------------------------------
    # JSONL 저장
    # --------------------------------------------------------

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for record in total_records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )
            file.write("\n")

    print()
    print("=" * 60)
    print("법령 파싱 완료")
    print("=" * 60)
    print(f"일반 조문: {article_count}")
    print(f"별표 chunk: {annex_chunk_count}")
    print(f"전체 record: {len(total_records)}")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
