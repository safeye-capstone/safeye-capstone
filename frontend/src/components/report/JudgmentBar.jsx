import {
  JUDGMENT_META,
  MANAGER_JUDGMENTS,
} from "../../constants/decisionState";

/**
 * 판정 분포 막대. counts는 countByJudgment / countsFromDecisionStates 결과.
 * 비율은 판정 불명을 뺀 위험+경고+안전 기준
 */
function JudgmentBar({ counts }) {
  const total = MANAGER_JUDGMENTS.reduce(
    (sum, key) => sum + (counts[key] ?? 0),
    0,
  );

  if (total === 0) {
    return (
      <p className="text-sm text-ink-3">
        위험·경고·안전으로 판정된 이벤트가 없습니다.
      </p>
    );
  }

  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden bg-line">
        {total > 0 &&
          MANAGER_JUDGMENTS.map((key) => {
            const count = counts[key] ?? 0;
            if (count === 0) return null;
            return (
              <div
                key={key}
                className={JUDGMENT_META[key].tone.solid}
                style={{ width: `${(count / total) * 100}%` }}
              />
            );
          })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-3">
        {MANAGER_JUDGMENTS.map((key) => {
          const { label, tone } = JUDGMENT_META[key];
          const count = counts[key] ?? 0;
          const percent = total > 0 ? Math.round((count / total) * 100) : 0;
          return (
            <div key={key} className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${tone.solid}`} />
              <span className="text-xs text-ink-3">{label}</span>
              <span className="text-xs font-semibold text-ink">{count}건</span>
              <span className="text-xs text-ink-3">({percent}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default JudgmentBar;
