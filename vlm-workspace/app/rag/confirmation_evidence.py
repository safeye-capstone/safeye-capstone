"""Explicit confirmation requirements, separate from candidate generation and model confidence."""
VISUAL_EVIDENCE_CODES = [
    'HEAD_VISIBLE', 'HELMET_ABSENT', 'ELEVATED_SUPPORT_VISIBLE', 'HARNESS_ABSENT',
    'ANCHOR_DISCONNECTED', 'EDGE_OR_OPENING_VISIBLE', 'PERSON_EXPOSED',
    'PROTECTION_MISSING', 'PASSAGE_VISIBLE', 'PASSAGE_BLOCKED', 'UNCERTAIN',
]


def assess_confirmation(hazard, workers, context):
    risk = hazard.get('risk_type')
    if risk == 'COLLAPSE':
        return True, []  # Existing continuous-video verifier remains authoritative.
    missing = []
    if hazard.get('confidence') not in {'MEDIUM', 'HIGH'}:
        missing.append('관찰 신뢰도가 LOW이거나 지정되지 않음')
    if hazard.get('candidate_source') == 'worker_supplement':
        missing.append('작업자 상태에서 자동 보완된 후보만으로는 확정할 수 없음')
    if context != 'INDUSTRIAL':
        missing.append('산업 작업 적용 맥락 확인 필요')
    if not str(hazard.get('evidence') or '').strip():
        missing.append('구체적인 관찰 설명 필요')
    codes = set(hazard.get('visual_evidence') or [])
    required = {
        'NO_HELMET': {'HEAD_VISIBLE', 'HELMET_ABSENT'},
        'UNFASTENED_SAFETY_HARNESS': {'ELEVATED_SUPPORT_VISIBLE'},
        'FALL_HAZARD': {'EDGE_OR_OPENING_VISIBLE', 'PERSON_EXPOSED', 'PROTECTION_MISSING'},
        'BLOCKED_PATH': {'PASSAGE_VISIBLE', 'PASSAGE_BLOCKED'},
    }.get(risk, set())
    absent = required - codes
    if absent:
        missing.append('필수 관찰 항목 부족: ' + ', '.join(sorted(absent)))
    if risk == 'UNFASTENED_SAFETY_HARNESS' and not codes & {'HARNESS_ABSENT', 'ANCHOR_DISCONNECTED'}:
        missing.append('안전대 미착용 또는 안전고리 미체결의 직접 관찰 필요')
    ids = hazard.get('worker_ids') or []
    by_id = {w.get('worker_id'): w for w in workers}
    valid_ids = bool(ids) and all(isinstance(i, int) and not isinstance(i, bool) and i in by_id for i in ids)
    linked = [by_id[i] for i in ids] if valid_ids else []
    if risk != 'BLOCKED_PATH' and not valid_ids:
        missing.append('동일 프레임에서 관찰 근거와 사람을 연결해야 함')
    if risk == 'NO_HELMET' and not any(w.get('helmet') == 'NOT_WEARING' for w in linked):
        missing.append('연결된 사람의 미착용 상태가 일치하지 않음')
    if risk == 'UNFASTENED_SAFETY_HARNESS' and not any(
        w.get('work_level') == 'ELEVATED' and (
            (w.get('harness') == 'NOT_WEARING' and 'HARNESS_ABSENT' in codes)
            or (w.get('harness') == 'WORN_NOT_CONNECTED' and 'ANCHOR_DISCONNECTED' in codes))
        for w in linked
    ):
        missing.append('같은 사람의 높은 지지면과 안전대 상태를 함께 확인해야 함')
    if hazard.get('context_review_required') or hazard.get('visual_review_required'):
        missing.append('관찰 모순 또는 시각 근거 검토가 남아 있음')
    return not missing, missing


def merge_frame_candidates(hazards, workers, context):
    """One record per risk per frame; never combine partial checks from different people."""
    groups = {}
    for hazard in hazards:
        eligible, missing = assess_confirmation(hazard, workers, context)
        hazard['confirmation_eligible'] = bool(hazard.get('detected')) and eligible
        hazard['confirmation_missing'] = missing
        groups.setdefault(hazard['risk_type'], []).append(hazard)
    merged = []
    ranks = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
    for risk, observations in groups.items():
        selected = max(observations, key=lambda h: (
            bool(h.get('detected')), bool(h.get('confirmation_eligible')),
            h.get('candidate_source') == 'vlm', ranks.get(h.get('confidence'), 1)))
        record = dict(selected)
        record['source_observations'] = [dict(h) for h in observations]
        record['observed_worker_ids'] = sorted({i for h in observations for i in h.get('worker_ids', [])
                                                 if isinstance(i, int) and not isinstance(i, bool)})
        merged.append(record)
    return merged
