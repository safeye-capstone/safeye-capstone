import {
  getSeverityBadge,
  getSeverityTone,
  normalizeSeverity,
} from "./severity";

// 판정 상태 목록과 라벨. 리포트 집계(ReportPage)에서 이 순서대로 표시한다
export const DECISION_STATES = [
  { key: "CONFIRMED", label: "확정 위험" },
  { key: "REVIEW_REQUIRED", label: "검토 대기" },
  { key: "REJECTED", label: "기각" },
  { key: "NO_DETECTION", label: "미탐지" },
  { key: "UNKNOWN", label: "판정 불명" },
];

const LABELS = Object.fromEntries(
  DECISION_STATES.map(({ key, label }) => [key, label]),
);

export const DECISION_STATE = {
  CONFIRMED: "CONFIRMED",
  REVIEW_REQUIRED: "REVIEW_REQUIRED",
  REJECTED: "REJECTED",
  NO_DETECTION: "NO_DETECTION",
};

// 경보 종류: SIREN은 빨간 토스트+사이렌, NOTICE는 노란 "확인 필요" 토스트
export const ALERT_KIND = {
  SIREN: "siren",
  NOTICE: "notice",
};

// 이벤트 한 건을 표시할 때 쓰는 스타일과 경보 종류.
// UNKNOWN은 여기 없다: 이벤트에서는 값이 없는 것과 같이 severity로 폴백한다
export const DECISION_META = {
  CONFIRMED: {
    label: LABELS.CONFIRMED,
    badgeClass: "bg-danger text-white border-transparent",
    tone: {
      text: "text-danger",
      border: "border-danger",
      box: "border-danger bg-danger-bg",
      solid: "bg-danger",
    },
    alertKind: ALERT_KIND.SIREN,
  },
  REVIEW_REQUIRED: {
    label: LABELS.REVIEW_REQUIRED,
    badgeClass: "bg-warn text-white border-transparent",
    tone: {
      text: "text-warn",
      border: "border-warn",
      box: "border-warn bg-warn-bg",
      solid: "bg-warn",
    },
    alertKind: ALERT_KIND.NOTICE,
  },
  REJECTED: {
    label: LABELS.REJECTED,
    badgeClass: "bg-muted text-white border-transparent",
    tone: {
      text: "text-muted",
      border: "border-border",
      box: "border-border bg-white",
      solid: "bg-muted",
    },
    alertKind: null,
  },
  NO_DETECTION: {
    label: LABELS.NO_DETECTION,
    badgeClass: "bg-safe text-white border-transparent",
    tone: {
      text: "text-safe",
      border: "border-safe",
      box: "border-safe bg-white",
      solid: "bg-safe",
    },
    alertKind: null,
  },
};

const isKnownState = (value) =>
  typeof value === "string" && Object.hasOwn(DECISION_META, value);

/**
 * 판정 상태를 읽는다. 최상위 decisionState가 있으면 먼저 쓰고,
 * 없으면 ragMetadata.vlm_decision_state를 읽는다.
 * 값이 없거나 모르는 값(UNKNOWN 포함)이면 null (severity 폴백 대상).
 */
export function getDecisionState(event) {
  const candidates = [
    event?.decisionState,
    event?.ragMetadata?.vlm_decision_state,
  ];
  return candidates.find(isKnownState) ?? null;
}

// 판정 값이 없을 때: 기존 severity 기준으로 표시와 경보를 정한다
function getSeverityFallback(event) {
  const severity = normalizeSeverity(event?.severity);
  const badge = getSeverityBadge(severity);

  let alertKind = ALERT_KIND.NOTICE;
  if (severity === "CRITICAL") alertKind = ALERT_KIND.SIREN;
  if (severity === "INFO") alertKind = null;

  return {
    state: null,
    label: badge.label,
    badgeClass: badge.className,
    tone: getSeverityTone(severity),
    alertKind,
  };
}

/** 화면 표시용 정보(라벨·배지·색·경보 종류)를 한 번에 돌려준다 */
export function getDecisionView(event) {
  const state = getDecisionState(event);
  if (!state) return getSeverityFallback(event);
  return { state, ...DECISION_META[state] };
}

/** 경보 대상이면 ALERT_KIND 값, 아니면 null */
export function getAlertKind(event) {
  return getDecisionView(event).alertKind;
}

export function isReviewRequired(event) {
  return getDecisionState(event) === DECISION_STATE.REVIEW_REQUIRED;
}
