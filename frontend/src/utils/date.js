/** Date 또는 "YYYY-MM-DD" 문자열을 "YYYY-MM-DD"로 변환합니다. */
export function toDateString(value) {
  if (typeof value === "string") return value;
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, "0");
  const d = String(value.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** "YYYY-MM-DD"에 일수를 더합니다. */
export function addDays(dateString, days) {
  const [y, m, d] = dateString.split("-").map(Number);
  const date = new Date(y, m - 1, d + days);
  return toDateString(date);
}

/** "2026-09-18" → "2026년 9월 18일 (금)" */
export function formatReportDate(dateString) {
  const [y, m, d] = dateString.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const day = ["일", "월", "화", "수", "목", "금", "토"][date.getDay()];
  return `${y}년 ${m}월 ${d}일 (${day})`;
}

/** 조회 가능한 마지막 날짜(어제)를 "YYYY-MM-DD"로 반환합니다. */
export function getYesterday() {
  const now = new Date();
  now.setDate(now.getDate() - 1);
  return toDateString(now);
}
