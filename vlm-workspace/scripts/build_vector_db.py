from pathlib import Path
import json

import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# 프로젝트 경로
# ============================================================

# vlm-workspace/
BASE_DIR = Path(__file__).resolve().parent.parent

# Vector DB 저장 위치
CHROMA_PATH = BASE_DIR / "data" / "rag" / "chroma_db"

# parse_articles.py가 생성하는 JSONL
JSONL_PATH = BASE_DIR / "data" / "parsed" / "regulations.jsonl"


# ============================================================
# Embedding Model
# ============================================================

EMBEDDING_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


# ============================================================
# document_type -> Chroma Collection
# ============================================================

COLLECTION_MAP = {
    # --------------------------------------------------------
    # 산업안전보건법 계열
    # --------------------------------------------------------
    "LAW": "osh_law",
    "ENFORCEMENT_DECREE": "osh_decree",
    "ENFORCEMENT_RULE": "osh_enforcement_rule",
    "SAFETY_REGULATION": "osh_safety_rule",

    # --------------------------------------------------------
    # 중대재해 처벌 등에 관한 법률
    # --------------------------------------------------------
    "SERIOUS_ACCIDENT_LAW": "serious_accident_law",

    # 시행령 본문
    "SERIOUS_ACCIDENT_DECREE": "serious_accident_decree",

    # 시행령 별표도 시행령과 같은 Collection에 저장
    "SERIOUS_ACCIDENT_DECREE_ANNEX": "serious_accident_decree",
}


# ============================================================
# JSONL Load
# ============================================================

def load_records() -> list[dict]:
    """regulations.jsonl 파일을 읽는다."""

    if not JSONL_PATH.exists():
        raise FileNotFoundError(
            "regulations.jsonl 파일을 찾을 수 없습니다.\n"
            f"경로: {JSONL_PATH}"
        )

    records = []

    with JSONL_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{line_number}번째 줄의 JSON이 잘못되었습니다."
                ) from error

    return records


# ============================================================
# Embedding Text 생성
# ============================================================

def build_embedding_text(record: dict) -> str:
    """
    임베딩 검색 품질을 높이기 위해

    법령명
    문서 종류
    조문
    별표
    본문

    정보를 함께 Embedding한다.
    """

    law_name = record.get("law_name", "")
    document_type = record.get("document_type", "")
    article = record.get("article", "")
    article_title = record.get("article_title", "")
    annex_no = record.get("annex_no", "")
    annex_title = record.get("annex_title", "")
    content = record.get("content", "")

    parts = [
        f"법령명: {law_name}",
        f"문서 종류: {document_type}",
    ]

    # --------------------------------------------------------
    # 일반 조문
    # --------------------------------------------------------

    if article:
        article_text = f"조항: {article}"

        if article_title:
            article_text += f" {article_title}"

        parts.append(article_text)

    # --------------------------------------------------------
    # 별표
    # --------------------------------------------------------

    if annex_no:
        annex_text = f"별표: {annex_no}"

        if annex_title:
            annex_text += f" {annex_title}"

        parts.append(annex_text)

    # --------------------------------------------------------
    # 실제 내용
    # --------------------------------------------------------

    parts.append(f"본문: {content}")

    return "\n".join(parts)


# ============================================================
# Collection 이름 결정
# ============================================================

def get_collection_name(record: dict) -> str | None:
    document_type = record.get("document_type")
    return COLLECTION_MAP.get(document_type)


# ============================================================
# Chroma metadata 생성
# ============================================================

def build_metadata(record: dict) -> dict:
    """
    ChromaDB metadata에는
    None 값을 넣지 않고 문자열로 통일한다.

    일반 조문과 별표를 동일 Collection에서
    구분할 수 있도록 annex 정보도 저장한다.
    """

    return {
        "law_name": str(record.get("law_name", "")),
        "document_type": str(record.get("document_type", "")),
        "article": str(record.get("article", "")),
        "article_title": str(record.get("article_title", "")),
        "annex_no": str(record.get("annex_no", "")),
        "annex_title": str(record.get("annex_title", "")),
        "source": str(record.get("source", "")),
    }


# ============================================================
# Collection 목록
# ============================================================

def get_collection_names() -> list[str]:
    """
    COLLECTION_MAP에서 중복 Collection 이름을 제거한다.

    SERIOUS_ACCIDENT_DECREE와
    SERIOUS_ACCIDENT_DECREE_ANNEX는
    둘 다 serious_accident_decree를 사용한다.
    """

    return list(dict.fromkeys(COLLECTION_MAP.values()))


# ============================================================
# Main
# ============================================================

def main() -> None:
    # --------------------------------------------------------
    # 경로 준비
    # --------------------------------------------------------

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # JSONL Load
    # --------------------------------------------------------

    records = load_records()

    print()
    print("=" * 60)
    print("Vector DB 구축 시작")
    print("=" * 60)
    print(f"JSONL 경로: {JSONL_PATH}")
    print(f"ChromaDB 경로: {CHROMA_PATH}")
    print(f"전체 record 수: {len(records)}")

    # ========================================================
    # Collection별 분리
    # ========================================================

    collection_names = get_collection_names()

    grouped_records = {
        collection_name: []
        for collection_name in collection_names
    }

    skipped_records = []

    for record in records:
        collection_name = get_collection_name(record)

        if collection_name is None:
            skipped_records.append(record)
            continue

        grouped_records[collection_name].append(record)

    # ========================================================
    # 문서 종류 통계
    # ========================================================

    print()
    print("=" * 60)
    print("Collection별 문서 수")
    print("=" * 60)

    for collection_name, items in grouped_records.items():
        print(f"{collection_name}: {len(items)}개")

    # ========================================================
    # 분류되지 않은 문서 표시
    # ========================================================

    if skipped_records:
        print()
        print("=" * 60)
        print("[경고] 분류되지 않은 record")
        print("=" * 60)
        print(f"총 {len(skipped_records)}개")

        document_types = sorted(
            {
                str(record.get("document_type", "UNKNOWN"))
                for record in skipped_records
            }
        )

        print("document_type:")

        for document_type in document_types:
            print(f"- {document_type}")

    # ========================================================
    # Embedding Model Load
    # ========================================================

    print()
    print("=" * 60)
    print("임베딩 모델 로딩")
    print("=" * 60)
    print(EMBEDDING_MODEL)

    model = SentenceTransformer(EMBEDDING_MODEL)

    # ========================================================
    # ChromaDB 초기화
    # ========================================================

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # ========================================================
    # 기존 Collection 삭제
    #
    # 전체 regulations.jsonl을 기준으로
    # 매번 DB를 완전히 재구축한다.
    # ========================================================

    print()
    print("=" * 60)
    print("기존 Collection 정리")
    print("=" * 60)

    for collection_name in collection_names:
        try:
            client.delete_collection(collection_name)
            print(f"삭제: {collection_name}")
        except Exception:
            print(f"없음: {collection_name}")

    # ========================================================
    # Collection별 Embedding + 저장
    # ========================================================

    for collection_name, collection_records in grouped_records.items():
        print()
        print("=" * 60)
        print(f"Collection 구축: {collection_name}")
        print("=" * 60)

        if not collection_records:
            print("데이터 없음 → 건너뜀")
            continue

        print(f"문서 수: {len(collection_records)}")

        # ----------------------------------------------------
        # Embedding documents
        # ----------------------------------------------------

        documents = [
            build_embedding_text(record)
            for record in collection_records
        ]

        # ----------------------------------------------------
        # Chroma IDs
        # ----------------------------------------------------

        ids = [
            record["chunk_id"]
            for record in collection_records
        ]

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        metadatas = [
            build_metadata(record)
            for record in collection_records
        ]

        # ----------------------------------------------------
        # Embedding
        # ----------------------------------------------------

        print("임베딩 생성 중...")

        embeddings = model.encode(
            documents,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,
        ).tolist()

        # ----------------------------------------------------
        # Collection 생성
        # ----------------------------------------------------

        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # ----------------------------------------------------
        # 작은 Batch로 Chroma 저장
        # ----------------------------------------------------

        batch_size = 100

        for start in range(0, len(collection_records), batch_size):
            end = min(start + batch_size, len(collection_records))

            collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                embeddings=embeddings[start:end],
            )

            print(f"저장: {end}/{len(collection_records)}")

        print(
            f"{collection_name} 저장 완료: "
            f"{collection.count()}개"
        )

    # ========================================================
    # 최종 확인
    # ========================================================

    print()
    print("=" * 60)
    print("최종 Collection 확인")
    print("=" * 60)

    available_collections = client.list_collections()

    for collection in available_collections:
        try:
            count = client.get_collection(collection.name).count()

        except AttributeError:
            # Chroma 버전에 따라
            # list_collections()가 문자열을
            # 반환하는 경우를 대비
            collection_name = str(collection)
            count = client.get_collection(collection_name).count()

            print(f"- {collection_name}: {count}개")
            continue

        print(f"- {collection.name}: {count}개")

    print()
    print("=" * 60)
    print("모든 Vector DB 구축 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
