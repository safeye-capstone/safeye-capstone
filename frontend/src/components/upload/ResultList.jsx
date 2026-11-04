import { Link } from "react-router-dom";
import { formatDate } from "../../utils/date";
import {
  getDecisionView,
  isReviewRequired,
} from "../../constants/decisionState";
import DecisionBadge from "../common/DecisionBadge";
import {
  parseRegulations,
  getReferenceRegulations,
} from "../../utils/regulation";
import { FEATURE_RESULT_DETAIL } from "../../constants/config";

function RegulationSection({ title, caption, regulations }) {
  if (regulations.length === 0) return null;

  return (
    <section className="mt-4 pl-3 border-l-2 border-border">
      <h3 className="text-xs font-semibold text-muted mb-1">{title}</h3>
      {caption && <p className="text-xs text-muted mb-1">{caption}</p>}
      {regulations.map(({ law, articles }) => (
        <div key={law} className="mb-1.5 last:mb-0">
          {law && <p className="text-xs text-muted">{law}</p>}
          <ul className="text-sm text-ink break-keep">
            {articles.map((article) => (
              <li key={article}>{article}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function ResultList({
  results = [],
  loading = false,
  error = null,
  emptyMessage = "사진을 올리면 분석 결과가 여기에 표시됩니다.",
  mediaType = null,
}) {
  if (loading) {
    return <div className="p-4 text-center text-muted">분석하는 중...</div>;
  }

  if (error) {
    return (
      <div className="p-4 text-center text-danger font-semibold bg-danger-bg border border-danger rounded-lg">
        {error}
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-[14.5px] font-bold mb-4">판단 결과</h2>
      {results.length === 0 ? (
        <p className="text-muted text-sm">{emptyMessage}</p>
      ) : (
        results.map((item) => {
          const { tone } = getDecisionView(item);
          const detectedLabel =
            formatDate(item.detectedAt) ?? formatDate(item.receivedAt);
          const violated = parseRegulations(item.violatedRegulation);
          const references = getReferenceRegulations(item);

          return (
            <article
              key={item.clientId ?? item.id}
              className={`border rounded-lg p-4 mb-3 ${tone.box}`}
            >
              <header className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3">
                <DecisionBadge event={item} />

                {item.zoneName && (
                  <span className="text-xs text-muted min-w-0 truncate">
                    {item.zoneName}
                  </span>
                )}
                {detectedLabel && (
                  <span className="text-xs text-muted">{detectedLabel}</span>
                )}
              </header>

              {isReviewRequired(item) && (
                <p className="mb-3 px-3 py-2 rounded-md border border-warn bg-white/70 text-sm font-semibold text-warn break-keep">
                  사람 확인 필요 — AI가 위험으로 확정하지 못한 건입니다.
                  현장에서 직접 확인해 주세요.
                </p>
              )}

              {mediaType === "video" && item.fileUrl && (
                <video
                  src={item.fileUrl}
                  controls
                  preload="metadata"
                  className="w-full max-h-[320px] rounded-md bg-black mb-3"
                />
              )}

              <p className="text-lg leading-relaxed text-ink whitespace-pre-wrap break-keep">
                {item.vlmDescription || "설명을 생성하지 못했습니다."}
              </p>

              <RegulationSection title="위반 규정" regulations={violated} />
              <RegulationSection
                title="참고 법령"
                caption="관련 법령 검색 결과이며, 위반이 확정된 것은 아닙니다."
                regulations={references}
              />

              {item.actionGuide && (
                <section className="mt-3 p-3 rounded-md bg-white/70">
                  <h3 className="text-xs font-semibold text-muted mb-1">
                    조치 방법
                  </h3>
                  <p className="text-sm text-ink whitespace-pre-wrap break-keep">
                    {item.actionGuide}
                  </p>
                </section>
              )}

              {FEATURE_RESULT_DETAIL && (
                <Link
                  to={`/history/${item.id}`}
                  className="inline-block mt-3 text-xs font-semibold text-accent no-underline"
                >
                  상세 보기
                </Link>
              )}
            </article>
          );
        })
      )}
    </div>
  );
}

export default ResultList;
