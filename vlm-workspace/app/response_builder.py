def unique_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        value = str(value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def get_detected_hazards(analysis: dict) -> list[dict]:
    return [hazard for hazard in analysis.get("hazards", []) if hazard.get("detected", False)]


def build_vlm_description(analysis: dict) -> str:
    scene = (analysis.get("scene_description", "") or "").strip()
    evidence = unique_strings(
        [hazard.get("evidence", "") for hazard in get_detected_hazards(analysis)]
    )
    parts = []
    if scene:
        parts.append(scene)
    if evidence:
        parts.append("위험 판단 근거: " + " / ".join(evidence[:3]))
    if not parts:
        return "이미지에서 명확한 위험 상황이 확인되지 않았습니다."
    return " ".join(parts)


def build_violated_regulation(regulations: list[dict]) -> str:
    if not regulations:
        return ""
    results = []
    seen = set()
    for regulation in regulations:
        metadata = regulation.get("metadata", {})
        law_name = metadata.get("law_name") or regulation.get("collection") or "법령"
        article = metadata.get("article") or ""
        article_title = metadata.get("article_title") or ""
        effective = metadata.get("effective") or metadata.get("effective_date") or ""
        key = (law_name, article)
        if key in seen:
            continue
        seen.add(key)
        text = f"{law_name} {article}".strip()
        if article_title:
            text += f"({article_title})"
        if effective:
            text += f" [시행 {effective}]"
        results.append(text)
        if len(results) >= 3:
            break
    return " / ".join(results)


def build_action_guide(analysis: dict, severity: str) -> str:
    risk_types = {hazard.get("risk_type") for hazard in get_detected_hazards(analysis)}
    actions = []
    if "UNFASTENED_SAFETY_HARNESS" in risk_types:
        actions.append(
            "즉시 고소작업을 중지하고 안전대 및 안전고리를 적절한 부착설비에 체결하세요."
        )
    if "FALL_HAZARD" in risk_types:
        actions.append(
            "작업발판, 안전난간, 개구부 방호 및 추락방호조치 상태를 확인하고 미비한 조치를 보완하세요."
        )
    if "NO_HELMET" in risk_types:
        actions.append("작업자에게 안전모를 즉시 착용시키고 정상 착용 상태를 확인하세요.")
    if "BLOCKED_PATH" in risk_types:
        actions.append("통행로의 자재와 장애물을 제거하여 안전한 이동경로를 확보하세요.")
    if severity == "CRITICAL":
        actions.append("현장 관리자에게 즉시 알리고 안전조치 확인 전까지 작업을 재개하지 마세요.")
    if not actions:
        return "추가적인 즉시 조치는 필요하지 않으며 현장을 지속적으로 모니터링하세요."
    return " ".join(unique_strings(actions))
