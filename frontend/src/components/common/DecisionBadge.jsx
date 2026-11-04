import { getDecisionView } from "../../constants/decisionState";

function DecisionBadge({ event }) {
  const { label, badgeClass } = getDecisionView(event);

  return (
    <span
      className={`inline-block text-xs font-bold px-2 py-0.5 rounded-full border whitespace-nowrap ${badgeClass}`}
    >
      {label}
    </span>
  );
}

export default DecisionBadge;
