import { Link } from "react-router-dom";
import { formatDate } from "../../utils/date";
import { getSeverityTone } from "../../constants/severity";
import SeverityBadge from "../common/SeverityBadge";
import { parseRegulations } from "../../utils/regulation";

function ResultList({
  results = [],
  loading = false,
  error = null,
  emptyMessage = "사진을 올리면 분석 결과가 여기에 표시됩니다.",
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
          const tone = getSeverityTone(item.severity);
          const detectedLabel =
            formatDate(item.detectedAt) ?? formatDate(item.receivedAt);
          const regulations = parseRegulations(item.violatedRegulation);

          return (
            <article
              key={item.clientId ?? item.id}
              className={`border rounded-lg p-4 mb-3 ${tone.box}`}
            >
              <header className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3">
                <SeverityBadge severity={item.severity} />

                {item.zoneName && (
                  <span className="text-xs text-muted min-w-0 truncate">
                    {item.zoneName}
                  </span>
                )}
                {detectedLabel && (
                  <span className="text-xs text-muted">{detectedLabel}</span>
                )}
              </header>

              <p className="text-lg leading-relaxed text-ink whitespace-pre-wrap break-keep">
                {item.vlmDescription || "설명을 생성하지 못했습니다."}
              </p>

              {regulations.length > 0 && (
                <section className="mt-4 pl-3 border-1-2 border-border">
                  <h3 className="text-xs font-semibold text-muted mb-1">
                    위반 규정
                  </h3>
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
              )}

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

              <Link
                to={`/history/${item.id}`}
                className="inline-block mt-3 text-xs font-semibold text-accent no-underline"
              >
                상세 보기
              </Link>
            </article>
          );
        })
      )}
    </div>
  );
}

export default ResultList;
