import { Link } from "react-router-dom";
import { formatDate } from "../utils/formatDate";

const SEVERITY_STYLE = {
  CRITICAL: {
    label: "심각",
    box: "border-danger bg-danger-bg",
    text: "text-danger",
  },
  WARNING: {
    label: "주의",
    box: "border-warn bg-warn-bg",
    text: "text-warn",
  },
  INFO: {
    label: "안전",
    box: "border-border bg-white",
    text: "text-safe",
  },
};

const UNKNOWN_STYLE = {
  label: "확인 필요",
  box: "border-border bg-white",
  text: "text-muted",
};

function ResultList({ results = [], loading = false, error = null }) {
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
        <p className="text-muted text-sm">
          사진을 올리면 분석 결과가 여기에 표시됩니다.
        </p>
      ) : (
        results.map((item) => {
          const style = SEVERITY_STYLE[item.severity] ?? UNKNOWN_STYLE;
          const detectedLabel =
            formatDate(item.detectedAt) ?? formatDate(item.receivedAt);

          return (
            <article
              key={item.clientId ?? item.id}
              className={`border rounded-lg p-4 mb-3 ${style.box}`}
            >
              <header className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3">
                <span
                  className={`text-xs font-bold px-2 y-0.5 rounded-full border border-current ${style.text}`}
                >
                  {style.label}
                </span>
                {item.zoneName && (
                  <span className="text-xs text-muted min-2-0 truncate">
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

              {item.violatedRegulation && (
                <section className="mt-4 pl-3 border-1-2 border-border">
                  <h3 className="text-xs font-semibold text-muted mb-1">
                    위반 규정
                  </h3>
                  <p className="text-sm text-ink whitespace-pre-wrap break-keep">
                    {item.violatedRegulation}
                  </p>
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

              {item.id && (
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
