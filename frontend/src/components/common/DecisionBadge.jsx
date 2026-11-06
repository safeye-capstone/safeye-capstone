import { getJudgmentView } from "../../constants/decisionState";

/*
 * 판정 배지
 * 모든 화면에 이것 하나만 사용
 * showUnknown: 판정 불명도 보여줄지 선택 (개발자: true)
 */

function DecisionBadge({ event, showUnknown = false, className = "" }) {
  const { label, Icon, badgeClass, hiddenForManager } = getJudgmentView(event);

  if (hiddenForManager && !showUnknown) return null;

  return (
    <span
      className={`inline-flex items-center gap-1 h-7 px-2.5 rounded-badge border text-sm font-bold whitespace-nowrap ${badgeClass} ${className}`}
    >
      <Icon size={14} strokeWidth={3} aria-hidden="true" />
      {label}
    </span>
  );
}

export default DecisionBadge;
