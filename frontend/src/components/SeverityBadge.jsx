import { SEVERITY_BADGE, UNKNOWN_BADGE } from "../constants/severity";

function SeverityBadge({ severity }) {
  const style = SEVERITY_BADGE[severity] ?? UNKNOWN_BADGE;

  return (
    <span
      className={`inline-block text-xs font-bold px-2 py-0.5 rounded-full border whitespace-nowrap ${style.className}`}
    >
      {style.label}
    </span>
  );
}

export default SeverityBadge;
