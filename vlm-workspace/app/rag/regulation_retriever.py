import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
# ============================================================
# 프로젝트 경로
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_PATH = BASE_DIR / "data" / "rag" / "chroma_db"
# ============================================================
# 임베딩 모델
# ============================================================
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# ============================================================
# ChromaDB Collection
# ============================================================
COLLECTION_NAMES = [
    "osh_law",
    "osh_decree",
    "osh_enforcement_rule",
    "osh_safety_rule",
    "serious_accident_law",
    "serious_accident_decree",
]
CANDIDATE_SOURCE_PRIORITY = {
    "vector": 0,
    "priority": 1,
    "serious_priority": 2,
    "annex_priority": 3,
}
# 중대재해처벌법 계열 Collection
SERIOUS_ACCIDENT_COLLECTIONS = {"serious_accident_law", "serious_accident_decree"}
# 중대재해처벌법/시행령을 우선 검색해야 하는
# 관리체계·경영책임자 중심 Query 표현.
#
# "사업주"처럼 산업안전보건법에도 광범위하게 등장하는
# 단어 하나만으로는 중대재해처벌법 Query로 판단하지 않는다.
SERIOUS_ACCIDENT_QUERY_KEYWORDS = [
    "중대재해",
    "중대산업재해",
    "중대시민재해",
    "경영책임자",
    "경영책임자등",
    "안전보건관리체계",
    "안전보건관리체계 구축",
    "안전 및 보건 확보의무",
    "안전보건 확보의무",
    "안전보건 확보",
    "유해·위험요인 확인",
    "유해 위험요인 확인",
    "유해위험요인 확인",
    "재해예방에 필요한 인력",
    "재해예방 인력",
    "안전보건 예산",
    "안전보건 관계법령",
    "도급·용역·위탁",
    "도급 용역 위탁",
    "안전보건 목표",
]
# ============================================================
# 중대재해처벌법 세부 Query -> 핵심 조항 규칙
# ============================================================
SERIOUS_ACCIDENT_RULES = [
    {
        "name": "SAFETY_HEALTH_MANAGEMENT_SYSTEM",
        "query_keywords": [
            "안전보건관리체계",
            "안전보건관리체계 구축",
            "유해·위험요인 확인",
            "유해 위험요인 확인",
            "유해위험요인 확인",
            "개선 절차",
            "개선절차",
            "재해예방에 필요한 인력",
            "재해예방 인력",
            "안전보건 예산",
            "안전보건 목표",
            "경영방침",
        ],
        "targets": [
            {
                "collection": "serious_accident_law",
                "article": "제4조",
                "bonus": 6.0,
            },
            {
                "collection": "serious_accident_decree",
                "article": "제4조",
                "bonus": 7.0,
            },
        ],
    },
    {
        "name": "LEGAL_DUTY_MANAGEMENT",
        "query_keywords": [
            "안전보건 관계법령",
            "안전·보건 관계 법령",
            "안전 보건 관계 법령",
            "관계 법령",
            "의무이행",
            "의무 이행",
            "반기 1회",
            "반기 1회 이상",
            "점검",
            "교육",
        ],
        "targets": [
            {
                "collection": "serious_accident_law",
                "article": "제4조",
                "bonus": 5.0,
            },
            {
                "collection": "serious_accident_decree",
                "article": "제5조",
                "bonus": 7.0,
            },
        ],
    },
    {
        "name": "RECURRENCE_PREVENTION",
        "query_keywords": [
            "재발방지",
            "재발 방지",
            "재발방지 대책",
            "재발 방지 대책",
        ],
        "targets": [
            {
                "collection": "serious_accident_law",
                "article": "제4조",
                "bonus": 6.0,
            },
        ],
    },
]
# ============================================================
# 시행령 별표 Query
# ============================================================
ANNEX_QUERY_PATTERN = re.compile("별표(?:\\s*[_\\-]?\\s*(\\d+))?")


def is_annex_query(
    query_text: str,
) -> bool:
    """
    Query가 시행령 별표 자체를 찾는 요청인지 확인한다.
    """
    return "별표" in query_text


def extract_requested_annex_no(
    query_text: str,
) -> str | None:
    """
    '별표 4', '별표4'처럼 번호가 명시된 경우
    metadata 형식인 '별표 4'로 정규화한다.
    """
    match = ANNEX_QUERY_PATTERN.search(query_text)
    if not match:
        return None
    number = match.group(1)
    if not number:
        return None
    return f"별표 {number}"


# ============================================================
# 위험 유형별 기본 규칙
# ============================================================
RISK_RULES = {
    # --------------------------------------------------------
    # 안전모 미착용
    # --------------------------------------------------------
    "NO_HELMET": {
        "positive_keywords": [
            "안전모",
            "보호구",
            "보호구의 지급",
            "보호구 착용",
            "착용",
            "머리",
            "낙하",
            "비래",
        ],
        "strong_keywords": [
            "안전모",
            "보호구의 지급",
        ],
        "priority_targets": [
            {
                "collection": "osh_safety_rule",
                "article": "제32조",
            },
        ],
        "negative_keywords": [
            "밀폐공간",
            "금형",
            "프레스",
            "터널",
            "공정안전보고서",
            "출입구의 임의잠김",
        ],
    },
    # --------------------------------------------------------
    # 안전대 미착용 / 안전고리 미체결
    # --------------------------------------------------------
    "UNFASTENED_SAFETY_HARNESS": {
        "positive_keywords": [
            "안전대",
            "안전고리",
            "부착설비",
            "체결",
            "미체결",
            "고소작업",
            "추락",
            "보호구",
            "착용",
        ],
        "strong_keywords": [
            "안전대",
            "부착설비",
            "안전대의 부착설비",
        ],
        # 제44조를 핵심으로 하되,
        # 안전대 미착용 상황에서는 제32조,
        # 일반 추락방지 맥락에서는 제42조도 후보로 포함한다.
        "priority_targets": [
            {
                "collection": "osh_safety_rule",
                "article": "제44조",
            },
            {
                "collection": "osh_safety_rule",
                "article": "제32조",
            },
            {
                "collection": "osh_safety_rule",
                "article": "제42조",
            },
        ],
        "negative_keywords": [
            "밀폐공간",
            "금형",
            "프레스",
            "터널",
            "공정안전보고서",
            "출입구의 임의잠김",
        ],
    },
    # --------------------------------------------------------
    # 추락 위험
    # --------------------------------------------------------
    "FALL_HAZARD": {
        "positive_keywords": [
            "추락",
            "작업발판",
            "안전난간",
            "개구부",
            "덮개",
            "안전대",
            "추락방호망",
            "부착설비",
            "고소작업",
            "높은 장소",
        ],
        "strong_keywords": [
            "추락의 방지",
            "개구부",
            "안전난간",
            "안전대",
            "부착설비",
            "작업발판",
            "추락방호망",
        ],
        "priority_targets": [
            {
                "collection": "osh_safety_rule",
                "article": "제42조",
            },
            {
                "collection": "osh_safety_rule",
                "article": "제43조",
            },
            {
                "collection": "osh_safety_rule",
                "article": "제44조",
            },
        ],
        "negative_keywords": [
            "금형조정",
            "금형",
            "프레스",
            "밀폐공간",
            "공정안전보고서",
            "낙반",
            "출수",
        ],
    },
    # --------------------------------------------------------
    # 통로 장애
    # --------------------------------------------------------
    "BLOCKED_PATH": {
        "positive_keywords": [
            "통로",
            "통로의 설치",
            "통행",
            "작업장 통로",
            "장애물",
            "출입구",
            "작업장의 출입구",
            "이동",
        ],
        "strong_keywords": [
            "통로의 설치",
            "작업장의 출입구",
            "통로",
            "통행",
        ],
        "priority_targets": [
            {
                "collection": "osh_safety_rule",
                "article": "제22조",
            },
            {
                "collection": "osh_safety_rule",
                "article": "제11조",
            },
        ],
        "negative_keywords": [
            "밀폐공간",
            "임의잠김",
            "인원의 점검",
            "금형",
            "프레스",
            "터널",
            "잠김 방지",
        ],
    },
}
# ============================================================
# 세부 상황별 조항 규칙
#
# 같은 FALL_HAZARD라도
# 실제 상황에 따라 가장 직접적인 조항을 구분한다.
# ============================================================
SCENARIO_RULES = {
    # --------------------------------------------------------
    # 안전대 미착용 / 안전고리 미체결
    # --------------------------------------------------------
    "UNFASTENED_SAFETY_HARNESS": [
        # 제44조: 안전대를 착용했지만 안전고리가
        # 부착설비에 연결되지 않은 경우를 가장 강하게 우선한다.
        {
            "name": "HARNESS_ANCHOR_NOT_CONNECTED",
            "query_keywords": [
                "안전고리",
                "부착설비",
                "체결하지",
                "체결되지",
                "미체결",
                "안전대 부착",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제44조",
                },
            ],
            "bonus": 7.0,
        },
        # 제32조: 고소작업 중 안전대 자체를 착용하지 않은 경우
        {
            "name": "HARNESS_NOT_WEARING",
            "query_keywords": [
                "안전대 미착용",
                "안전대를 착용하지",
                "안전대 착용하지",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제32조",
                },
            ],
            "bonus": 6.0,
        },
        # 제42조: 일반적인 고소작업/추락 방지 맥락
        {
            "name": "HARNESS_GENERAL_FALL_PREVENTION",
            "query_keywords": [
                "고소작업",
                "추락",
                "높이 2미터",
                "높은 장소",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제42조",
                },
            ],
            "bonus": 2.0,
        },
    ],
    "FALL_HAZARD": [
        # ----------------------------------------------------
        # 제43조
        # 개구부 / 난간 / 덮개
        # ----------------------------------------------------
        {
            "name": "OPENING_GUARD",
            "query_keywords": [
                "개구부",
                "안전난간",
                "난간",
                "덮개",
                "작업발판 끝",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제43조",
                },
            ],
            "bonus": 4.0,
        },
        # ----------------------------------------------------
        # 제44조
        # 안전대 부착설비
        # ----------------------------------------------------
        {
            "name": "SAFETY_BELT_ANCHOR",
            "query_keywords": [
                "안전대",
                "부착설비",
                "걸이",
                "걸 곳",
                "안전대 부착",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제44조",
                },
            ],
            "bonus": 4.0,
        },
        # ----------------------------------------------------
        # 제42조
        # 일반 추락 / 작업발판 / 추락방호망
        # ----------------------------------------------------
        {
            "name": "GENERAL_FALL_PREVENTION",
            "query_keywords": [
                "작업발판",
                "추락방호망",
                "방호망",
                "높은 장소",
                "고소작업",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제42조",
                },
            ],
            # 제43 / 제44보다 조금 낮게 설정
            # 세부 상황이 명확하면 더 구체적인 조항을 우선하기 위함
            "bonus": 2.0,
        },
    ],
    "BLOCKED_PATH": [
        {
            "name": "PASSAGE_OBSTRUCTION",
            "query_keywords": [
                "통로",
                "통행",
                "장애물",
                "적치",
                "자재",
                "막혀",
                "방해",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제22조",
                },
            ],
            "bonus": 4.0,
        },
        {
            "name": "WORKPLACE_ENTRANCE",
            "query_keywords": [
                "출입구",
                "출입문",
                "출입",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제11조",
                },
            ],
            "bonus": 3.0,
        },
    ],
    "NO_HELMET": [
        {
            "name": "NO_SAFETY_HELMET",
            "query_keywords": [
                "안전모",
                "헬멧",
                "머리 보호",
                "미착용",
                "착용하지",
            ],
            "targets": [
                {
                    "collection": "osh_safety_rule",
                    "article": "제32조",
                },
            ],
            "bonus": 4.0,
        },
    ],
}
# ============================================================
# Risk Type 마커
# ============================================================
RISK_MARKER_PATTERN = re.compile(
    r"\[RISK_TYPE=" r"(NO_HELMET|UNFASTENED_SAFETY_HARNESS|" r"FALL_HAZARD|BLOCKED_PATH)" r"\]"
)


# ============================================================
# 임베딩 모델
# ============================================================
@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """첫 검색 시 한 번만 임베딩 모델을 로드한다."""
    logger.info("RAG 임베딩 모델 로딩: %s", EMBEDDING_MODEL)
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_chroma_client() -> Any:
    """첫 검색 시 ChromaDB 경로를 검증하고 클라이언트를 생성한다."""
    if not CHROMA_PATH.exists():
        raise FileNotFoundError(f"ChromaDB를 찾을 수 없습니다.\n경로: {CHROMA_PATH}")
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


# ============================================================
# Collection 목록
# ============================================================
def get_available_collections() -> list[str]:
    return [collection.name for collection in get_chroma_client().list_collections()]


# ============================================================
# Risk Type 추출
# ============================================================
def extract_risk_type(
    query: str,
) -> tuple[str | None, str]:
    match = RISK_MARKER_PATTERN.search(query)
    if not match:
        return (None, query.strip())
    risk_type = match.group(1)
    clean_query = RISK_MARKER_PATTERN.sub("", query).strip()
    return (risk_type, clean_query)


# ============================================================
# 중대재해처벌법 관리체계 Query 판정
# ============================================================
def is_serious_accident_query(
    query_text: str,
) -> bool:
    """
    단순 현장 위험이 아니라
    중대재해처벌법의 경영책임자 의무,
    안전보건관리체계, 인력·예산·점검 등
    관리체계 중심 질의인지 판정한다.
    """
    query_lower = query_text.lower()
    return any((keyword.lower() in query_lower for keyword in SERIOUS_ACCIDENT_QUERY_KEYWORDS))


# ============================================================
# 중대재해처벌법 세부 Query 가점 계산
# ============================================================
def calculate_serious_accident_bonus(
    candidate: dict[str, Any],
    query_text: str,
) -> tuple[float, list[str]]:
    """
    관리체계 질의에서 단순히 중대재해처벌법 Collection 전체에
    동일한 가점을 주지 않고, 실제 핵심 조항에 추가 가점을 준다.
    """
    query_lower = query_text.lower()
    collection_name = candidate.get("collection", "")
    metadata = candidate.get("metadata", {})
    article = metadata.get("article", "")
    total_bonus = 0.0
    matched_rules = []
    for rule in SERIOUS_ACCIDENT_RULES:
        query_matches = [
            keyword for keyword in rule["query_keywords"] if keyword.lower() in query_lower
        ]
        if not query_matches:
            continue
        for target in rule["targets"]:
            if target["collection"] == collection_name and target["article"] == article:
                multiplier = 1.0 + (min(len(query_matches), 3) - 1) * 0.15
                bonus = float(target["bonus"]) * multiplier
                total_bonus += bonus
                matched_rules.append(rule["name"])
    return (total_bonus, list(dict.fromkeys(matched_rules)))


# ============================================================
# 중대재해처벌법 핵심 조항 직접 후보 추가
# ============================================================
def fetch_serious_accident_priority_candidates(
    query_text: str,
    query_embedding: list[float],
) -> list[dict[str, Any]]:
    """
    Vector 검색 결과에 핵심 조항이 포함되지 않는 경우를 막기 위해
    관리체계 Query에서 관련 핵심 조항을 직접 후보군에 추가한다.
    """
    if not is_serious_accident_query(query_text):
        return []
    query_lower = query_text.lower()
    target_keys = []
    for rule in SERIOUS_ACCIDENT_RULES:
        if not any(keyword.lower() in query_lower for keyword in rule["query_keywords"]):
            continue
        for target in rule["targets"]:
            key = (target["collection"], target["article"])
            if key not in target_keys:
                target_keys.append(key)
    # 관리체계 Query인데 세부 규칙이 애매한 경우에도
    # 법 제4조 / 시행령 제4조를 기본 후보로 포함한다.
    if not target_keys:
        target_keys = [("serious_accident_law", "제4조"), ("serious_accident_decree", "제4조")]
    results = []
    for (
        collection_name,
        article,
    ) in target_keys:
        try:
            collection = get_chroma_client().get_collection(name=collection_name)
            response = collection.get(
                where={"article": article},
                include=[
                    "documents",
                    "metadatas",
                    "embeddings",
                ],
            )
        except Exception:
            logger.exception(
                "RAG 핵심 조항 조회 오류 - collection=%s article=%s", collection_name, article
            )
            continue
        results.extend(
            build_candidates_from_get_response(
                response=response,
                collection_name=collection_name,
                query_embedding=query_embedding,
                candidate_source="serious_priority",
            )
        )
    return results


# ============================================================
# 시행령 별표 후보 직접 추가
# ============================================================
def fetch_annex_candidates(
    query_text: str,
    query_embedding: list[float],
) -> list[dict[str, Any]]:
    """
    Query에 '별표'가 명시된 경우
    serious_accident_decree Collection에서
    별표 record를 직접 후보군에 추가한다.
    별표 번호가 있으면 해당 별표만 조회하고,
    번호가 없으면 전체 별표를 대상으로 Vector distance를 계산한다.
    """
    if not is_annex_query(query_text):
        return []
    requested_annex_no = extract_requested_annex_no(query_text)
    try:
        collection = get_chroma_client().get_collection(name="serious_accident_decree")
        if requested_annex_no:
            where = {"annex_no": requested_annex_no}
        else:
            where = {"document_type": "SERIOUS_ACCIDENT_DECREE_ANNEX"}
        response = collection.get(where=where, include=["documents", "metadatas", "embeddings"])
    except Exception:
        logger.exception("RAG 별표 조회 오류")
        return []
    return build_candidates_from_get_response(
        response=response,
        collection_name="serious_accident_decree",
        query_embedding=query_embedding,
        candidate_source="annex_priority",
    )


# ============================================================
# Query 임베딩
# ============================================================
def embed_query(
    query: str,
) -> list[float]:
    embedding = get_embedding_model().encode(query, normalize_embeddings=True)
    return embedding.tolist()


# ============================================================
# Cosine Distance
# ============================================================
def cosine_distance(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    similarity = sum((a * b for a, b in zip(vector_a, vector_b)))
    return 1.0 - similarity


def build_candidates_from_get_response(
    response: dict[str, Any],
    collection_name: str,
    query_embedding: list[float],
    candidate_source: str,
) -> list[dict[str, Any]]:
    """ChromaDB get 결과를 공통 후보 형식으로 안전하게 변환한다."""
    ids = response.get("ids", []) or []
    documents = response.get("documents", []) or []
    metadatas = response.get("metadatas", []) or []
    embeddings = response.get("embeddings")
    if embeddings is None:
        embeddings = []
    item_count = min(len(ids), len(documents), len(metadatas), len(embeddings))
    if item_count < len(ids):
        logger.warning(
            "RAG 후보 데이터 개수 불일치 - collection=%s ids=%d documents=%d "
            "metadatas=%d embeddings=%d",
            collection_name,
            len(ids),
            len(documents),
            len(metadatas),
            len(embeddings),
        )
    return [
        {
            "id": ids[index],
            "collection": collection_name,
            "document": documents[index],
            "metadata": metadatas[index] or {},
            "distance": float(cosine_distance(query_embedding, embeddings[index])),
            "candidate_source": candidate_source,
        }
        for index in range(item_count)
    ]


# ============================================================
# Vector Search
# ============================================================
def search_collection(
    collection_name: str,
    query_embedding: list[float],
    top_k: int = 12,
) -> list[dict[str, Any]]:
    collection = get_chroma_client().get_collection(name=collection_name)
    count = collection.count()
    if count == 0:
        return []
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(
            top_k,
            count,
        ),
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )
    ids = result.get("ids", [[]])[0] or []
    documents = result.get("documents", [[]])[0] or []
    metadatas = result.get("metadatas", [[]])[0] or []
    distances = result.get("distances", [[]])[0] or []
    results = []
    for index, item_id in enumerate(ids):
        results.append(
            {
                "id": item_id,
                "collection": collection_name,
                "document": documents[index],
                "metadata": metadatas[index] or {},
                "distance": float(distances[index]),
                "candidate_source": "vector",
            }
        )
    return results


# ============================================================
# Priority Candidate 직접 추가
# ============================================================
def fetch_priority_candidates(
    risk_type: str | None,
    query_embedding: list[float],
) -> list[dict[str, Any]]:
    if risk_type not in RISK_RULES:
        return []
    results = []
    for target in RISK_RULES[risk_type]["priority_targets"]:
        collection_name = target["collection"]
        article = target["article"]
        try:
            collection = get_chroma_client().get_collection(name=collection_name)
            response = collection.get(
                where={"article": article},
                include=["documents", "metadatas", "embeddings"],
            )
        except Exception:
            logger.exception(
                "RAG 우선 조항 조회 오류 - collection=%s article=%s",
                collection_name,
                article,
            )
            continue
        results.extend(
            build_candidates_from_get_response(
                response=response,
                collection_name=collection_name,
                query_embedding=query_embedding,
                candidate_source="priority",
            )
        )
    return results


# ============================================================
# Candidate 병합
# ============================================================
def merge_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[Any, Any], dict[str, Any]] = {}
    for candidate in candidates:
        key = (candidate.get("collection"), candidate.get("id"))
        if key not in merged:
            merged[key] = candidate
            continue
        current_source = merged[key].get("candidate_source", "vector")
        new_source = candidate.get("candidate_source", "vector")
        if CANDIDATE_SOURCE_PRIORITY.get(new_source, 0) > CANDIDATE_SOURCE_PRIORITY.get(
            current_source, 0
        ):
            merged[key]["candidate_source"] = new_source
    return list(merged.values())


# ============================================================
# Candidate 전체 텍스트
# ============================================================
def build_candidate_text(
    candidate: dict[str, Any],
) -> str:
    metadata = candidate.get("metadata", {})
    return (
        f"{metadata.get('law_name', '')} "
        f"{metadata.get('document_type', '')} "
        f"{metadata.get('article', '')} "
        f"{metadata.get('article_title', '')} "
        f"{metadata.get('annex_no', '')} "
        f"{metadata.get('annex_title', '')} "
        f"{candidate.get('document', '')}"
    ).lower()


# ============================================================
# Vector Score
# ============================================================
def distance_to_score(
    distance: float | None,
) -> float:
    if distance is None:
        return 0.0
    return 1.0 / (1.0 + max(distance, 0))


# ============================================================
# 정확한 Priority Target 확인
# ============================================================
def is_priority_target(
    candidate: dict[str, Any],
    risk_type: str,
) -> bool:
    collection = candidate.get("collection")
    article = candidate.get("metadata", {}).get("article")
    for target in RISK_RULES[risk_type]["priority_targets"]:
        if target["collection"] == collection and target["article"] == article:
            return True
    return False


# ============================================================
# 세부 Scenario Score 계산
# ============================================================
def calculate_scenario_bonus(
    candidate: dict[str, Any],
    risk_type: str | None,
    query_text: str,
) -> tuple[float, list[str]]:
    if risk_type not in SCENARIO_RULES:
        return (0.0, [])
    collection = candidate.get("collection")
    article = candidate.get("metadata", {}).get("article", "")
    query_lower = query_text.lower()
    total_bonus = 0.0
    matched_scenarios = []
    for scenario in SCENARIO_RULES[risk_type]:
        # Query에서 실제 등장한 세부 키워드
        query_matches = [
            keyword for keyword in scenario["query_keywords"] if keyword.lower() in query_lower
        ]
        if not query_matches:
            continue
        for target in scenario["targets"]:
            if target["collection"] == collection and target["article"] == article:
                # 해당 scenario 키워드가 여러 개 나오면
                # 보너스 소폭 증가
                keyword_multiplier = 1.0 + (min(len(query_matches), 3) - 1) * 0.2
                bonus = scenario["bonus"] * keyword_multiplier
                total_bonus += bonus
                matched_scenarios.append(scenario["name"])
    return (total_bonus, matched_scenarios)


# ============================================================
# Reranking
# ============================================================
def rerank_candidate(
    candidate: dict[str, Any],
    risk_type: str | None,
    query_text: str,
) -> dict[str, Any]:
    vector_score = distance_to_score(candidate.get("distance"))
    collection_name = candidate.get("collection", "")
    serious_collection = collection_name in SERIOUS_ACCIDENT_COLLECTIONS
    serious_query = is_serious_accident_query(query_text)
    # ========================================================
    # Risk marker가 없는 일반 검색
    #
    # 중대재해 관리체계 질의라면
    # 중대재해처벌법/시행령을 우선한다.
    # ========================================================
    if risk_type not in RISK_RULES:
        score = vector_score
        metadata = candidate.get("metadata", {})
        annex_no = metadata.get("annex_no", "")
        annex_query = is_annex_query(query_text)
        requested_annex_no = extract_requested_annex_no(query_text)
        collection_adjustment = 0.0
        if serious_query and serious_collection:
            collection_adjustment += 2.5
        # ----------------------------------------------------
        # 별표 Query 조정
        # ----------------------------------------------------
        annex_bonus = 0.0
        if annex_query:
            # 실제 별표 record를 강하게 우선한다.
            if annex_no:
                annex_bonus += 6.0
                # "별표 4"처럼 번호까지 명시한 경우
                # 정확한 별표 번호를 추가 우선한다.
                if requested_annex_no:
                    if annex_no == requested_annex_no:
                        annex_bonus += 8.0
                    else:
                        annex_bonus -= 2.0
            # 별표를 찾는 Query인데 일반 시행령 조문이면 감점
            elif serious_collection:
                annex_bonus -= 2.0
        score += collection_adjustment + annex_bonus
        (
            serious_bonus,
            serious_matched_rules,
        ) = calculate_serious_accident_bonus(
            candidate,
            query_text,
        )
        score += serious_bonus
        priority_target = bool(serious_bonus > 0 or annex_bonus > 0)
        return {
            **candidate,
            "vector_score": round(vector_score, 6),
            "rerank_score": round(score, 6),
            "matched_keywords": [],
            "title_matches": [],
            "matched_scenarios": [],
            "scenario_bonus": 0.0,
            "serious_accident_bonus": round(serious_bonus, 4),
            "serious_matched_rules": serious_matched_rules,
            "annex_query": annex_query,
            "requested_annex_no": requested_annex_no or "",
            "annex_bonus": round(annex_bonus, 4),
            "penalty_keywords": [],
            "priority_target": priority_target,
            "domain_relevant": True,
            "serious_accident_query": serious_query,
            "collection_adjustment": round(collection_adjustment, 4),
        }
    rule = RISK_RULES[risk_type]
    metadata = candidate.get("metadata", {})
    article_title = metadata.get("article_title", "") or ""
    article_title_lower = article_title.lower()
    candidate_text = build_candidate_text(candidate)
    query_lower = query_text.lower()
    # ========================================================
    # 1. Vector similarity
    # ========================================================
    score = vector_score * 1.5
    # ========================================================
    # 2. Query와 Document 양쪽에 있는 키워드만 가점
    # ========================================================
    matched_keywords = []
    for keyword in rule["positive_keywords"]:
        keyword_lower = keyword.lower()
        if keyword_lower in query_lower and keyword_lower in candidate_text:
            matched_keywords.append(keyword)
            score += 0.40
    # ========================================================
    # 3. Query keyword + Article Title 정확 일치
    # ========================================================
    title_matches = []
    for keyword in rule["strong_keywords"]:
        keyword_lower = keyword.lower()
        if keyword_lower in query_lower and keyword_lower in article_title_lower:
            title_matches.append(keyword)
            score += 2.0
    # ========================================================
    # 4. 기본 Priority Target
    # ========================================================
    priority_target = is_priority_target(candidate, risk_type)
    if priority_target:
        score += 1.0
    # ========================================================
    # 5. 구체적인 현장 Scenario
    # ========================================================
    scenario_bonus, matched_scenarios = calculate_scenario_bonus(candidate, risk_type, query_text)
    score += scenario_bonus
    # ========================================================
    # 6. 안전보건기준 규칙 가점
    #
    # 이미지에서 직접 탐지한 현장 위험은
    # 구체적 안전조치 조항이 있는
    # 산업안전보건기준에 관한 규칙을 우선한다.
    # ========================================================
    if collection_name == "osh_safety_rule":
        score += 0.25
    # ========================================================
    # 7. 중대재해처벌법 Collection 조정
    #
    # FALL_HAZARD / NO_HELMET / BLOCKED_PATH 같은
    # 개별 현장 위험은 그 자체만으로
    # 중대재해처벌법 위반이라고 단정할 수 없다.
    #
    # 따라서 일반 이미지 위험 Query에서는
    # 중대재해처벌법 계열을 감점한다.
    #
    # 반대로 Query가 안전보건관리체계,
    # 경영책임자 의무 등 관리체계를 명시하면 가점한다.
    # ========================================================
    collection_adjustment = 0.0
    if serious_collection:
        if serious_query:
            collection_adjustment += 2.5
        else:
            collection_adjustment -= 2.0
    score += collection_adjustment
    # ========================================================
    # 8. 무관한 분야 감점
    # ========================================================
    penalty_keywords = []
    for keyword in rule["negative_keywords"]:
        if keyword.lower() in candidate_text:
            penalty_keywords.append(keyword)
            score -= 1.0
    # ========================================================
    # 9. 관련성
    # ========================================================
    domain_relevant = bool(
        priority_target
        or matched_keywords
        or title_matches
        or matched_scenarios
        or (serious_query and serious_collection)
    )
    if not domain_relevant:
        score -= 1.0
    return {
        **candidate,
        "vector_score": round(vector_score, 6),
        "rerank_score": round(score, 6),
        "matched_keywords": list(dict.fromkeys(matched_keywords)),
        "title_matches": list(dict.fromkeys(title_matches)),
        "matched_scenarios": matched_scenarios,
        "scenario_bonus": round(scenario_bonus, 4),
        "penalty_keywords": list(dict.fromkeys(penalty_keywords)),
        "priority_target": priority_target,
        "domain_relevant": domain_relevant,
        "serious_accident_query": serious_query,
        "collection_adjustment": round(collection_adjustment, 4),
    }


# ============================================================
# 중복 제거
# ============================================================
def remove_duplicates(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    일반 조문은 법령명 + 조문으로 중복 제거한다.
    별표는 article 값이 비어 있으므로
    기존 방식대로라면 동일 법령의 모든 별표가
    하나로 합쳐지는 문제가 있다.
    따라서 별표는 법령명 + 별표 번호를 기준으로
    가장 높은 점수의 chunk 하나만 유지한다.
    """
    seen = set()
    unique = []
    for result in results:
        metadata = result.get("metadata", {})
        law_name = metadata.get("law_name", "")
        article = metadata.get("article", "")
        annex_no = metadata.get("annex_no", "")
        if article:
            key = (law_name, "article", article)
        elif annex_no:
            key = (law_name, "annex", annex_no)
        else:
            # 조문/별표 정보가 없는 예외 record는
            # Chroma ID까지 포함해 잘못된 중복 제거를 피한다.
            key = (law_name, "record", result.get("id", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


# ============================================================
# 전체 검색
# ============================================================
def search_regulations(
    query: str,
    final_top_k: int = 5,
    per_collection_k: int = 3,
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query or final_top_k <= 0:
        return []
    # --------------------------------------------------------
    # Risk Type
    # --------------------------------------------------------
    risk_type, clean_query = extract_risk_type(query)
    logger.info("RAG 위험 유형: %s", risk_type or "UNKNOWN")
    # --------------------------------------------------------
    # Query Embedding
    # --------------------------------------------------------
    query_embedding = embed_query(clean_query)
    # --------------------------------------------------------
    # Vector 후보
    # --------------------------------------------------------
    candidate_per_collection = max(per_collection_k, 12)
    candidates = []
    available_collections = set(get_available_collections())
    for collection_name in COLLECTION_NAMES:
        if collection_name not in available_collections:
            logger.warning("RAG Collection 없음: %s", collection_name)
            continue
        try:
            candidates.extend(
                search_collection(
                    collection_name,
                    query_embedding,
                    candidate_per_collection,
                )
            )
        except Exception:
            logger.exception("RAG 검색 오류 - collection=%s", collection_name)
    # --------------------------------------------------------
    # Priority 후보 추가
    # --------------------------------------------------------
    candidates.extend(fetch_priority_candidates(risk_type, query_embedding))
    # 중대재해처벌법 관리체계 Query에서는
    # 법 제4조, 시행령 제4조/제5조 등 핵심 조항을
    # Vector Top-K 누락 여부와 상관없이 후보군에 직접 포함한다.
    candidates.extend(fetch_serious_accident_priority_candidates(clean_query, query_embedding))
    # Query가 시행령 별표를 명시하면
    # 별표 record를 직접 후보군에 추가한다.
    candidates.extend(fetch_annex_candidates(clean_query, query_embedding))
    # --------------------------------------------------------
    # 중복 병합
    # --------------------------------------------------------
    candidates = merge_candidates(candidates)
    # --------------------------------------------------------
    # Query-aware Reranking
    # --------------------------------------------------------
    reranked = [rerank_candidate(candidate, risk_type, clean_query) for candidate in candidates]
    reranked.sort(key=lambda item: item.get("rerank_score", -9999), reverse=True)
    reranked = remove_duplicates(reranked)
    # --------------------------------------------------------
    # 별표 번호가 직접 지정된 경우
    #
    # 예:
    # "시행령 별표 4를 찾고 싶다"
    #
    # 이 경우 다른 별표나 일반 조문으로 Top-K를 채우지 않고,
    # 요청한 별표 번호와 정확히 일치하는 결과만 반환한다.
    #
    # 반대로:
    # "시행령의 별표 기준을 찾고 싶다"
    #
    # 처럼 번호가 없는 경우에는 기존처럼 여러 별표를
    # 의미 기반으로 검색한다.
    # --------------------------------------------------------
    requested_annex_no = extract_requested_annex_no(clean_query)
    if requested_annex_no:
        exact_annex_results = [
            result
            for result in reranked
            if (result.get("metadata", {}).get("annex_no", "") == requested_annex_no)
        ]
        if exact_annex_results:
            logger.info("RAG 별표 번호 직접 지정: %s -> 해당 별표만 반환", requested_annex_no)
            return exact_annex_results[:final_top_k]
        logger.warning("RAG 요청 별표를 찾지 못했습니다: %s", requested_annex_no)
        return []
    # --------------------------------------------------------
    # 관련 후보 우선
    # --------------------------------------------------------
    relevant = [result for result in reranked if result.get("domain_relevant", False)]
    fallback = [result for result in reranked if not result.get("domain_relevant", False)]
    final_results = relevant + fallback
    return final_results[:final_top_k]


# ============================================================
# 테스트 출력
# ============================================================
def print_search_results(
    results: list[dict[str, Any]],
) -> None:
    if not results:
        print("관련 법령을 찾지 못했습니다.")
        return
    print()
    print("=" * 60)
    print("관련 산업안전 법령")
    print("=" * 60)
    for index, result in enumerate(
        results,
        start=1,
    ):
        metadata = result.get("metadata", {})
        law_name = metadata.get("law_name", "법령명 없음")
        article = metadata.get("article", "")
        article_title = metadata.get("article_title", "")
        annex_no = metadata.get("annex_no", "")
        annex_title = metadata.get("annex_title", "")
        print()
        print(f"[{index}] {law_name}")
        if article:
            print(f"조항: {article} {article_title}")
        elif annex_no:
            print(f"별표: {annex_no} {annex_title}")
        else:
            print("조항/별표: 정보 없음")
        print(f"Collection: {result.get('collection')}")
        distance = result.get("distance")
        if distance is not None:
            print(f"Vector distance: {distance:.4f}")
        print(f"Rerank score: {result.get('rerank_score', 0):.4f}")
        matched_keywords = result.get("matched_keywords", [])
        if matched_keywords:
            print("Query 일치 키워드: " + ", ".join(matched_keywords))
        title_matches = result.get("title_matches", [])
        if title_matches:
            print("조문 제목 일치: " + ", ".join(title_matches))
        scenarios = result.get("matched_scenarios", [])
        if scenarios:
            print("상황 매칭: " + ", ".join(scenarios))
            print(f"상황 가점: +{result.get('scenario_bonus', 0):.2f}")
        collection_adjustment = result.get("collection_adjustment", 0.0)
        if collection_adjustment:
            sign = "+" if collection_adjustment > 0 else ""
            print(f"Collection 조정: {sign}{collection_adjustment:.2f}")
        if result.get("serious_accident_query", False):
            print("중대재해 관리체계 Query: YES")
        serious_rules = result.get("serious_matched_rules", [])
        if serious_rules:
            print("중대재해 핵심 조항 매칭: " + ", ".join(serious_rules))
            print(f"중대재해 조항 가점: +{result.get('serious_accident_bonus', 0):.2f}")
        if result.get("annex_query", False):
            print("시행령 별표 Query: YES")
            requested_annex_no = result.get("requested_annex_no", "")
            if requested_annex_no:
                print(f"요청 별표: {requested_annex_no}")
            annex_bonus = result.get("annex_bonus", 0.0)
            if annex_bonus:
                sign = "+" if annex_bonus > 0 else ""
                print(f"별표 가점: {sign}{annex_bonus:.2f}")
        if result.get("priority_target", False):
            print("핵심 조항: YES")
        print(f"후보 출처: {result.get('candidate_source')}")


# ============================================================
# 직접 실행
# ============================================================
def main() -> None:
    print()
    print(f"ChromaDB 경로: {CHROMA_PATH}")
    print("사용 가능한 Collection:")
    for name in get_available_collections():
        print(f"- {name}")
    while True:
        print()
        query = input("검색할 위험 상황 (종료: q): ").strip()
        if query.lower() == "q":
            break
        if not query:
            continue
        results = search_regulations(query=query, final_top_k=3, per_collection_k=12)
        print_search_results(results)


if __name__ == "__main__":
    main()
