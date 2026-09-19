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
