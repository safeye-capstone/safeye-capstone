import { Check, Circle, Minus, TriangleAlert } from "lucide-react";

/*
 * 판정 규칙은 이 파일에만 두기
 * VLM 값 -> 판정(위험/경고/안전/판정 불명) -> 화면 정보(라벨, 색, 아이콘, 경보)
 */

// VLM이 보내는 값
export const DECISION_STATE = {
  CONFIRMED: "CONFIRMED",
  REVIEW_REQUIRED: "REVIEW_REQUIRED",
  REJECTED: "REJECTED",
  NO_DETECTION: "NO_DETECTION",
};

// 화면 판정
export const JUDGMENT = {
  DANGER: "DANGER",
  WARNING: "WARNING",
  SAFE: "SAFE",
  UNKNOWN: "UNKNOWN",
};

// 경보 종류: SIREN: 빨간 토스트+사이렌  NOTICE: 노란색 확인 필요 토스트
export const ALERT_KIND = {
  SIREN: "siren",
  NOTICE: "notice",
};

// REJECTED는 AI 재검증이 틀릴 수 있어 사람이 확인하도록 경고로 둔다 (멘토링 결정)
const STATE_TO_JUDGMENT = {
  [DECISION_STATE.CONFIRMED]: JUDGMENT.DANGER,
  [DECISION_STATE.REVIEW_REQUIRED]: JUDGMENT.WARNING,
  [DECISION_STATE.REJECTED]: JUDGMENT.WARNING,
  [DECISION_STATE.NO_DETECTION]: JUDGMENT.SAFE,
};

export const JUDGMENT_META = {
  [JUDGMENT.DANGER]: {
    label: "위험",
    Icon: TriangleAlert,
    badgeClass: "bg-danger text-on-danger border-danger",
    tone: {
      text: "text-danger",
      border: "border-danger",
      box: "border-danger bg-danger-bg",
      solid: "bg-danger",
    },
    alertKind: ALERT_KIND.SIREN,
    hiddenForManager: false,
  },
  [JUDGMENT.WARNING]: {
    label: "경고",
    Icon: Circle,
    badgeClass: "bg-warn text-on-warn border-warn",
    tone: {
      text: "text-warn-strong",
      border: "border-warn",
      box: "border-warn bg-warn-bg",
      solid: "bg-warn",
    },
    alertKind: ALERT_KIND.NOTICE,
    hiddenForManager: false,
  },
  [JUDGMENT.SAFE]: {
    label: "안전",
    Icon: Check,
    badgeClass: "bg-white text-safe border-safe",
    tone: {
      text: "text-safe",
      border: "border-safe",
      box: "border-line bg-white",
      solid: "bg-safe",
    },
    alertKind: null,
    hiddenForManager: false,
  },
  [JUDGMENT.UNKNOWN]: {
    label: "판정 불명",
    Icon: Minus,
    badgeClass: "bg-canvas text-ink-3 border-line",
    tone: {
      text: "text-ink-3",
      border: "border-line",
      box: "border-line bg-canvas",
      solid: "bg-ink-3",
    },
    alertKind: null,
    hiddenForManager: true,
  },
};

// 원본 값별 집계 순서와 라벨 (리포트 판정 분포에서 사용).
// REVIEW_REQUIRED와 REJECTED는 둘 다 "경고"이고, 개발자 화면에서만 나눠 본다
export const DECISION_STATES = [
  { key: "CONFIRMED", label: "위험", judgment: JUDGMENT.DANGER },
  {
    key: "REVIEW_REQUIRED",
    label: "경고 · 검토 대기",
    judgment: JUDGMENT.WARNING,
  },
  { key: "REJECTED", label: "경고 · 기각", judgment: JUDGMENT.WARNING },
  { key: "NO_DETECTION", label: "안전", judgment: JUDGMENT.SAFE },
  { key: "UNKNOWN", label: "판정 불명", judgment: JUDGMENT.UNKNOWN },
];

// 최상위 decisionState에 값이 있으면 그것만 보고, 없을 때만 ragMetadata를 본다
function readRawState(event) {
  const top = event?.decisionState;
  if (top !== undefined && top !== null && top !== "") return top;
  return event?.ragMetadata?.vlm_decision_state ?? null;
}

// 알고 있는 원본 판정 값(DECISION_STATE 중 하나), 아니면 null
export function getDecisionState(event) {
  const raw = readRawState(event);
  if (typeof raw !== "string") return null;
  const key = raw.trim().toUpperCase();
  return Object.hasOwn(STATE_TO_JUDGMENT, key) ? key : null;
}

// JUDGMENT 값. 모르면 UNKNOWN (severity로 대신 판단하지 않는다)
export function getJudgment(event) {
  const state = getDecisionState(event);
  return state ? STATE_TO_JUDGMENT[state] : JUDGMENT.UNKNOWN;
}

// 화면 표시용 정보를 한 번에 돌려준다
export function getJudgmentView(event) {
  const state = getDecisionState(event);
  const judgment = state ? STATE_TO_JUDGMENT[state] : JUDGMENT.UNKNOWN;
  return { state, judgment, ...JUDGMENT_META[judgment] };
}

// 경보 대상이면 ALERT_KIND 값, 아니면 null
export function getAlertKind(event) {
  return getJudgmentView(event).alertKind;
}

export function isReviewRequired(event) {
  return getJudgment(event) === JUDGMENT.WARNING;
}

// 안전 관리자 화면에 보이는 판정 (표시 순서)
export const MANAGER_JUDGMENTS = [
  JUDGMENT.DANGER,
  JUDGMENT.WARNING,
  JUDGMENT.SAFE,
];

/** 안전 관리자 화면에 보여도 되는 건인지 (판정 불명은 false) */
export function isVisibleToManager(event) {
  return !JUDGMENT_META[getJudgment(event)].hiddenForManager;
}

function emptyCounts() {
  return {
    [JUDGMENT.DANGER]: 0,
    [JUDGMENT.WARNING]: 0,
    [JUDGMENT.SAFE]: 0,
    [JUDGMENT.UNKNOWN]: 0,
  };
}

/** 이벤트 목록을 판정별로 센다 (대시보드, 이력) */
export function countByJudgment(items = []) {
  const counts = emptyCounts();
  for (const item of items) counts[getJudgment(item)] += 1;
  return counts;
}

/*
 * 리포트의 summary.decisionStateCounts(원본 값별 건수)를 판정별로 합친다.
 * REVIEW_REQUIRED + REJECTED = 경고, 모르는 키는 판정 불명
 */
export function countsFromDecisionStates(stateCounts) {
  const counts = emptyCounts();
  for (const [key, value] of Object.entries(stateCounts ?? {})) {
    const judgment = STATE_TO_JUDGMENT[key] ?? JUDGMENT.UNKNOWN;
    counts[judgment] += Number(value) || 0;
  }
  return counts;
}

// 기존 호출부 호환용. 화면을 모두 옮기면 삭제
export const getDecisionView = getJudgmentView;
