/** 1. 설명문이 아주 긴 경우 — 카드가 잘리거나 넘치는지 확인 */
export const CASE_LONG = {
  id: "9f3a1c20-4b77-4e0e-8a11-2d5c6e7f8a90",
  isDanger: true,
  zoneName: "A동 타설구역",
  severity: "CRITICAL",
  fileUrl: "http://localhost:8080/uploads/images/9f3a1c20.jpg",
  vlmDescription:
    "화면 중앙의 작업자가 안전모를 착용하지 않은 상태로 타설 구역 내부를 이동하고 있습니다. 해당 작업자는 콘크리트 펌프카의 붐대 하부를 통과하고 있으며, 붐대는 현재 가동 중인 것으로 보입니다. 펌프카 붐대 하부는 배관 이탈이나 콘크리트 낙하가 발생할 수 있는 구간으로, 작업자 출입이 통제되어야 하는 위치입니다.\n\n또한 우측 하단의 작업자 두 명은 안전대를 착용하고 있으나 걸이 설비에 체결하지 않은 상태입니다. 작업 발판 단부에 안전난간이 설치되어 있지 않아, 체결하지 않은 안전대는 실질적인 추락 방지 기능을 하지 못합니다.\n\n종합하면 이 장면에는 낙하물에 의한 맞음 위험과 추락 위험이 동시에 존재하며, 특히 붐대 하부 통행은 즉시 중지가 필요한 수준의 위험으로 판단됩니다.",
  violatedRegulation:
    "산업안전보건기준에 관한 규칙 제32조(보호구의 지급 등) 및 제42조(추락의 방지), 제20조(출입의 금지 등) 제9호 — 콘크리트 타설작업 중 거푸집 붕괴 위험이 있는 장소",
  actionGuide:
    "1. 붐대 하부 통행 작업자를 즉시 대피시키고 펌프카 가동을 중지하십시오.\n2. 붐대 작업 반경에 출입금지 표지와 방호선을 설치하십시오.\n3. 안전대 착용 작업자는 걸이 설비 체결 여부를 확인한 뒤 작업을 재개하십시오.\n4. 작업 발판 단부에 안전난간을 설치하십시오.",
  ragMetadata: { source: "산업안전보건기준에 관한 규칙", score: 0.91 },
  isResolved: false,
  detectedAt: "2026-09-09T02:14:33.512Z",
  resolvedAt: null,
};

/** 2. 안전 판정(INFO) — 정책 변경으로 안전 건도 DB에 저장됩니다 */
export const CASE_SAFE = {
  id: "7b2e5d91-8f43-4a6c-9e20-1a3b4c5d6e7f",
  isDanger: false,
  zoneName: "B동 자재창고",
  severity: "INFO",
  fileUrl: "http://localhost:8080/uploads/images/1c8d2f44.jpg",
  vlmDescription:
    "작업자 두 명이 안전모와 안전화를 착용한 상태로 자재를 적치하고 있습니다. 적치 높이는 안정적이며 통로 확보 상태도 양호합니다. 특이 위험 요소가 관찰되지 않습니다.",
  violatedRegulation: "",
  actionGuide: "",
  ragMetadata: null,
  isResolved: false,
  detectedAt: "2026-09-09T03:05:12.447Z",
  resolvedAt: null,
};

/** 3. 위험이지만 VLM이 일부 필드를 비워 보낸 경우 */
export const CASE_EMPTY = {
  id: "4e6b8a02-3c19-4d7f-b5a8-0f1e2d3c4b5a",
  isDanger: true,
  zoneName: "C동 용접구역",
  severity: "WARNING",
  fileUrl: "http://localhost:8080/uploads/images/4e6b8a02.jpg",
  vlmDescription: "용접 작업 중 불티 비산 방지 덮개가 확인되지 않습니다.",
  violatedRegulation: null,
  actionGuide: null,
  ragMetadata: {},
  isResolved: false,
  detectedAt: "2026-09-09T02:41:07.883Z",
  resolvedAt: null,
};

// ragMetadata.related_regulations 한 건의 모양 (vlm-workspace/app/image_pipeline.py 기준)
const regulation = (id, article, articleTitle) => ({
  id,
  collection: "mock",
  metadata: {
    law_name: "산업안전보건기준에 관한 규칙",
    article,
    article_title: articleTitle,
  },
});

const REG_HELMET = regulation("reg-032", "제32조", "보호구의 지급 등");
const REG_FALL = regulation("reg-042", "제42조", "추락의 방지");
const REG_OPENING = regulation("reg-043", "제43조", "개구부 등의 방호 조치");
const REG_FIRE = regulation("reg-241", "제241조", "화재위험작업 시의 준수사항");

const REVIEW_NOTICE =
  "검토 대기: 위험 후보는 원본 이미지와 현장 상황을 추가 확인해야 합니다.";
const REVIEW_ACTION =
  "검토 대기 후보는 현장 담당자가 확인하고 필요한 안전조치를 판단해 주세요.";

/** 4. 확정 위험(CRITICAL) + 검토 후보가 함께 있는 경우 — 빨강, 사이렌 대상 */
export const CASE_CONFIRMED = {
  id: "a1c4e7f0-2b35-4d68-9a71-3e5f7b9d1c20",
  isDanger: true,
  zoneName: "A동 타설구역",
  severity: "CRITICAL",
  fileUrl: "http://localhost:8080/uploads/images/a1c4e7f0.jpg",
  vlmDescription: `작업자 한 명이 안전모를 착용하지 않은 상태로 비계 위에서 작업하고 있습니다. ${REVIEW_NOTICE} 후보 관찰 근거: 바닥 개구부 덮개가 일부 열려 있는 것으로 보임`,
  violatedRegulation:
    "산업안전보건기준에 관한 규칙 제32조(보호구의 지급 등), 제42조(추락의 방지)",
  actionGuide: `1. 해당 작업자의 작업을 즉시 중지시키고 안전모를 착용하게 하십시오.\n2. 비계 단부의 안전난간 설치 상태를 확인하십시오. ${REVIEW_ACTION}`,
  ragMetadata: {
    vlm_decision_state: "CONFIRMED",
    analysis_source: "single_image",
    hazards: [{ detected: true, evidence: "안전모 미착용 작업자 1명" }],
    related_regulations: [REG_HELMET, REG_FALL, REG_OPENING],
    confirmed_regulations: [REG_HELMET, REG_FALL],
    review_required_regulations: [REG_OPENING],
    raw_hazards: [],
  },
  isResolved: false,
  detectedAt: "2026-10-03T01:12:40.120Z",
  resolvedAt: null,
};

/** 5. 검토 대기 — isDanger가 true로 오지만 확정이 아님. 노랑, "확인 필요" 대상 */
export const CASE_REVIEW = {
  id: "b2d5f8a1-3c46-4e79-8b82-4f6a8c0e2d31",
  isDanger: true,
  zoneName: "C동 용접구역",
  severity: "WARNING",
  fileUrl: "http://localhost:8080/uploads/images/b2d5f8a1.jpg",
  vlmDescription: `작업자가 용접 작업을 하고 있으며 주변에 자재가 쌓여 있습니다. ${REVIEW_NOTICE} 후보 관찰 근거: 불티 비산 방지 덮개가 화면에서 확인되지 않음 / 소화기 위치가 가려져 있음`,
  violatedRegulation: "",
  actionGuide: REVIEW_ACTION,
  ragMetadata: {
    vlm_decision_state: "REVIEW_REQUIRED",
    analysis_source: "single_image",
    hazards: [{ detected: true, evidence: "불티 비산 방지 덮개 미확인" }],
    related_regulations: [REG_FIRE],
    confirmed_regulations: [],
    review_required_regulations: [REG_FIRE],
    raw_hazards: [],
  },
  isResolved: false,
  detectedAt: "2026-10-03T01:25:03.774Z",
  resolvedAt: null,
};

/** 6. AI가 오탐으로 기각 — 실제로는 영상에서만 발생. 회색, 경보 없음 */
export const CASE_REJECTED = {
  id: "c3e6a9b2-4d57-4f80-9c93-5a7b9d1f3e42",
  isDanger: false,
  zoneName: "B동 자재창고",
  severity: "INFO",
  fileUrl: "http://localhost:8080/uploads/images/c3e6a9b2.jpg",
  vlmDescription:
    "추락 위험 후보가 감지되었으나 재검증 결과 작업자가 안전난간 안쪽에 있는 것으로 확인되어 기각했습니다.",
  violatedRegulation: "",
  actionGuide: "",
  ragMetadata: {
    vlm_decision_state: "REJECTED",
    related_regulations: [],
  },
  isResolved: false,
  detectedAt: "2026-10-03T01:40:55.009Z",
  resolvedAt: null,
};

/** 7. 위험 후보 없음 — 초록, 경보 없음 */
export const CASE_NO_DETECTION = {
  id: "d4f7b0c3-5e68-4a91-8da4-6b8c0e2a4f53",
  isDanger: false,
  zoneName: "B동 자재창고",
  severity: "INFO",
  fileUrl: "http://localhost:8080/uploads/images/d4f7b0c3.jpg",
  vlmDescription:
    "작업자 세 명이 모두 안전모와 안전화를 착용하고 있으며 통로가 확보되어 있습니다.",
  violatedRegulation: "",
  actionGuide: "",
  ragMetadata: {
    vlm_decision_state: "NO_DETECTION",
    analysis_source: "single_image",
    hazards: [],
    related_regulations: [],
    confirmed_regulations: [],
    review_required_regulations: [],
    raw_hazards: [],
  },
  isResolved: false,
  detectedAt: "2026-10-03T02:02:18.336Z",
  resolvedAt: null,
};

/** 8. 최상위 decisionState만 있는 경우 — 백엔드가 필드를 추가한 뒤의 모양. 확정+WARNING */
export const CASE_TOP_LEVEL = {
  id: "e5a8c1d4-6f79-4b02-9eb5-7c9d1f3b5a64",
  isDanger: true,
  zoneName: "A동 타설구역",
  severity: "WARNING",
  decisionState: "CONFIRMED",
  fileUrl: "http://localhost:8080/uploads/images/e5a8c1d4.jpg",
  vlmDescription: "작업자 한 명이 안전화를 착용하지 않고 있습니다.",
  violatedRegulation: "산업안전보건기준에 관한 규칙 제32조(보호구의 지급 등)",
  actionGuide: "해당 작업자에게 안전화를 지급하고 착용을 확인하십시오.",
  ragMetadata: null,
  isResolved: false,
  detectedAt: "2026-10-03T02:15:47.901Z",
  resolvedAt: null,
};

/** 9. 판정 값이 UNKNOWN — 값이 없는 것과 같이 severity 기준으로 폴백 */
export const CASE_UNKNOWN = {
  id: "f6b9d2e5-7a80-4c13-8fc6-8d0e2a4c6b75",
  isDanger: true,
  zoneName: "C동 용접구역",
  severity: "WARNING",
  fileUrl: "http://localhost:8080/uploads/images/f6b9d2e5.jpg",
  vlmDescription: "용접 작업 구역 주변에 가연성 자재가 놓여 있습니다.",
  violatedRegulation: "",
  actionGuide: "",
  ragMetadata: { vlm_decision_state: "UNKNOWN" },
  isResolved: false,
  detectedAt: "2026-10-03T02:30:09.258Z",
  resolvedAt: null,
};

export const MOCK_RESULTS = [
  CASE_CONFIRMED,
  CASE_REVIEW,
  CASE_REJECTED,
  CASE_NO_DETECTION,
  CASE_TOP_LEVEL,
  CASE_UNKNOWN,
  CASE_LONG,
  CASE_SAFE,
  CASE_EMPTY,
];
