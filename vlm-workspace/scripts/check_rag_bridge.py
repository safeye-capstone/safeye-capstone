import json

from app.rag.query_builder import build_search_query
from app.rag.regulation_retriever import search_regulations


def main() -> None:
    hazard = {
        "risk_type": "NO_HELMET",
        "detected": True,
        "confidence": "HIGH",
        "detection_count": 3,
        "evidence_frames": [
            "frame_0000.00.jpg",
            "frame_0002.00.jpg",
            "frame_0004.00.jpg",
        ],
        "evidence": ["작업자가 안전모를 착용하지 않고 작업 중"],
    }

    print("\n" + "=" * 60)
    print("RAG 연결 테스트")
    print("=" * 60)

    query = build_search_query(hazard)
    print(f"\n검색문:\n{query}")

    regulations = search_regulations(
        query=query,
        final_top_k=5,
        per_collection_k=3,
    )
    print("\n검색 결과:")
    print(json.dumps(regulations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
