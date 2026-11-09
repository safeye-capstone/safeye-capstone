"""Project internal analysis metadata onto the backend/frontend response contract."""
from copy import deepcopy

HAZARD_FIELDS = (
    "risk_type", "final_decision", "vlm_decision_state", "final_decision_reason",
    "is_primary_hazard", "parent_risk_type", "related_hazards",
    "review_order", "review_order_reason", "review_group", "review_proximity",
)
QUEUE_FIELDS = (
    "review_order", "hazard_index", "risk_type", "review_group",
    "review_proximity", "review_order_reason",
)
REGULATION_FIELDS = ("law_name", "article", "article_title")


def select_fields(record, fields):
    return {key: deepcopy(record[key]) for key in fields if key in record}


def regulation_summaries(regulations):
    summaries = []
    seen = set()
    for regulation in regulations:
        metadata = select_fields(regulation.get("metadata") or {}, REGULATION_FIELDS)
        if not any(metadata.values()):
            continue
        key = tuple(metadata.get(field) for field in REGULATION_FIELDS)
        if key not in seen:
            summaries.append({"metadata": metadata})
            seen.add(key)
    return summaries


def collapse_summary(verification):
    summary = select_fields(verification, ("status",))
    # Requested windows are not proof that footage was actually analyzed.
    summary["clips"] = [
        select_fields(clip, ("start", "end")) for clip in verification.get("clips", [])
        if clip.get("status") in {None, "ANALYZED"}
        and clip.get("start") is not None and clip.get("end") is not None
    ]
    summary["events"] = [
        select_fields(event, ("suspected_start_seconds", "decision_seconds"))
        for event in verification.get("events", [])
    ]
    return summary


def build_public_metadata(metadata):
    """Keep decisions, reference labels and review order without exposing diagnostics."""
    if metadata is None:
        return None
    public = select_fields(metadata, ("vlm_decision_state", "review_order_policy"))
    hazards = metadata.get("hazards", [])
    if "hazards" in metadata:
        # Keep array positions, including secondary/rejected records, for hazard_index.
        public["hazards"] = [select_fields(hazard, HAZARD_FIELDS) for hazard in hazards]
        for hazard, record in zip(hazards, public["hazards"]):
            verification = hazard.get("collapse_verification")
            if hazard.get("risk_type") == "COLLAPSE" and isinstance(verification, dict):
                record["collapse_verification"] = collapse_summary(verification)
    if "review_queue" in metadata:
        public["review_queue"] = [
            select_fields(item, QUEUE_FIELDS) for item in metadata["review_queue"]
        ]
    if "review_required_regulations" in metadata:
        public["review_required_regulations"] = regulation_summaries(
            metadata["review_required_regulations"]
        )
    elif "related_regulations" in metadata:
        # Preserve the frontend's fallback only when the preferred key is absent.
        public["related_regulations"] = regulation_summaries(metadata["related_regulations"])
    elif "hazards" in metadata:
        # Video reference results previously lived inside detailed hazard records.
        public["review_required_regulations"] = regulation_summaries([
            regulation for hazard in hazards
            if hazard.get("final_decision") == "REVIEW_REQUIRED"
            for regulation in hazard.get("regulations", [])
        ])
    return public
