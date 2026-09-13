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

/** 2. 안전 판정(INFO) — DB에 저장되지 않아 id·detectedAt이 비어서 옵니다 */
export const CASE_SAFE = {
  id: null,
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
  detectedAt: null,
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

export const MOCK_RESULTS = [CASE_LONG, CASE_SAFE, CASE_EMPTY];
