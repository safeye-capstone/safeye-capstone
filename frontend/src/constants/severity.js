export const SEVERITY_BADGE = {
  CRITICAL: {
    label: "심각",
    className: "bg-danger text-white border-transparent",
  },
  WARNING: {
    label: "주의",
    className: "bg-warn text-white border-transparent",
  },
  INFO: {
    label: "안전",
    className: "bg-white text-muted border-border",
  },
};

export const UNKNOWN_BADGE = {
  label: "확인 필요",
  className: "bg-white text-muted border-border",
};

export const SEVERITY_ORDER = ["CRITICAL", "WARNING", "INFO"];

export const SEVERITY_TONE = {
  CRITICAL: {
    text: "text-danger",
    border: "border-danger",
    box: "border-danger bg-danger-bg",
    solid: "bg-danger",
  },
  WARNING: {
    text: "text-warn",
    border: "border-warn",
    box: "border-warn bg-warn-bg",
    solid: "bg-warn",
  },
  INFO: {
    text: "text-safe",
    border: "border-border",
    box: "border-border bg-white",
    solid: "bg-safe",
  },
};

const UNKNOWN_TONE = {
  text: "text-muted",
  border: "border-border",
  box: "border-border bg-white",
  solid: "bg-muted",
};

export function normalizeSeverity(severity) {
  if (severity?.startsWith("CRITICAL")) return "CRITICAL";
  return severity;
}

export function getSeverityBadge(severity) {
  return SEVERITY_BADGE[normalizeSeverity(severity)] ?? UNKNOWN_BADGE;
}

export function getSeverityTone(severity) {
  return SEVERITY_TONE[normalizeSeverity(severity)] ?? UNKNOWN_TONE;
}

export function isAlertSeverity(severity) {
  const s = normalizeSeverity(severity);
  return s === "CRITICAL" || s === "WARNING";
}
