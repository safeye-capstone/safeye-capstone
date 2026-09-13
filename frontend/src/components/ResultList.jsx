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


function ResultList({
  results = [],
  loading = false,
  error = null,
}) {
  if (loading) {
    return (
      <div className="p-4 text-center text-muted">
        분석하는 중...
      </div>
    );
  }


  if (error) {
    return (
      <div className="p-4 text-center text-danger font-semibold bg-danger-bg border border-danger rounded-lg">
        {error}
      </div>
    );
  }


  return (
    <div
      className="
        bg-white
        border
        border-border
        rounded-[14px]
        p-6
      "
    >
      <h2 className="text-[14.5px] font-bold mb-4">
        분석 결과
      </h2>


      {results.length === 0 ? (
        <p className="text-muted text-sm">
          아직 분석 결과가 없습니다.
        </p>
      ) : (
        results.map((item, index) => {
          const style =
            SEVERITY_STYLE[item.severity]
            ?? UNKNOWN_STYLE;

          const detectedLabel =
            formatDate(item.detectedAt)
            ?? formatDate(item.receivedAt);


          return (
            <article
              key={item.clientId ?? item.id ?? index}
              className={`border rounded-lg p-4 mb-3 ${style.box}`}
            >
              {/* 위험도 / 구역 / 시간 */}
              <header className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3">
                <span
                  className={`
                    text-xs
                    font-bold
                    px-2
                    py-0.5
                    rounded-full
                    border
                    border-current
                    ${style.text}
                  `}
                >
                  {style.label}
                </span>


                {item.zoneName && (
                  <span className="text-xs text-muted min-w-0 truncate">
                    {item.zoneName}
                  </span>
                )}


                {detectedLabel && (
                  <span className="text-xs text-muted">
                    {detectedLabel}
                  </span>
                )}
              </header>


              {/* 위험 여부 */}
              <div className="text-sm mb-3">
                <span className="font-semibold text-ink">
                  위험 여부:
                </span>{" "}

                <span
                  className={
                    item.isDanger
                      ? "text-danger font-semibold"
                      : "text-safe font-semibold"
                  }
                >
                  {item.isDanger
                    ? "위험 감지"
                    : "안전"}
                </span>
              </div>


              {/* AI 분석 */}
              <section className="mb-3">
                <h3 className="text-xs font-semibold text-muted mb-1">
                  AI 분석
                </h3>

                <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-keep">
                  {item.vlmDescription
                    || "설명을 생성하지 못했습니다."}
                </p>
              </section>


              {/* 관련 법령 */}
              {item.violatedRegulation && (
                <section className="mt-4 pl-3 border-l-2 border-border">
                  <h3 className="text-xs font-semibold text-muted mb-1">
                    관련 법령
                  </h3>

                  <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-keep">
                    {item.violatedRegulation}
                  </p>
                </section>
              )}


              {/* 권장 조치 */}
              {item.actionGuide && (
                <section className="mt-3 p-3 rounded-md bg-white/70">
                  <h3 className="text-xs font-semibold text-muted mb-1">
                    권장 조치
                  </h3>

                  <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-keep">
                    {item.actionGuide}
                  </p>
                </section>
              )}


              {/* 상세 보기 */}
              {item.id && (
                <Link
                  to={`/history/${item.id}`}
                  className="inline-block mt-3 text-xs font-semibold text-accent no-underline"
                >
                  상세 보기 →
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