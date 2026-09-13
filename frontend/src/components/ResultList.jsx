import {
  Link,
} from "react-router-dom";


const SEVERITY_STYLE = {

  CRITICAL: {
    label: "심각",
    box:
      "border-danger bg-danger-bg",
    text:
      "text-danger",
  },

  WARNING: {
    label: "주의",
    box:
      "border-warn bg-warn-bg",
    text:
      "text-warn",
  },

  INFO: {
    label: "안전",
    box:
      "border-border bg-white",
    text:
      "text-safe",
  },

};


function ResultList({
  results = [],
}) {

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

      <h2
        className="
          text-[14.5px]
          font-bold
          mb-4
        "
      >
        분석 결과
      </h2>


      {results.length === 0 ? (

        <p
          className="
            text-muted
            text-sm
          "
        >
          아직 분석 결과가 없습니다.
        </p>

      ) : (

        results.map(
          (
            item,
            index
          ) => {

            const style =
              SEVERITY_STYLE[
                item.severity
              ]
              ?? SEVERITY_STYLE.INFO;


            return (

              <div
                key={
                  item.id
                  ?? index
                }
                className={`
                  border
                  rounded-lg
                  p-4
                  mb-3
                  ${style.box}
                `}
              >

                {/* =========================================
                    위험도 / 구역
                ========================================= */}

                <div
                  className="
                    flex
                    items-center
                    gap-2
                    mb-3
                  "
                >

                  <span
                    className={`
                      font-bold
                      ${style.text}
                    `}
                  >
                    {style.label}
                  </span>


                  {item.zoneName && (

                    <span
                      className="
                        text-xs
                        text-muted
                      "
                    >
                      · {item.zoneName}
                    </span>

                  )}

                </div>


                {/* =========================================
                    위험 여부
                ========================================= */}

                <div
                  className="
                    text-sm
                    mb-3
                  "
                >

                  <span
                    className="
                      font-semibold
                      text-ink
                    "
                  >
                    위험 여부:
                  </span>{" "}

                  <span
                    className={
                      item.isDanger
                        ? "text-danger font-semibold"
                        : "text-safe font-semibold"
                    }
                  >
                    {
                      item.isDanger
                        ? "위험 감지"
                        : "안전"
                    }
                  </span>

                </div>


                {/* =========================================
                    VLM 분석 설명
                ========================================= */}

                {item.vlmDescription && (

                  <div
                    className="
                      mb-3
                    "
                  >

                    <p
                      className="
                        text-xs
                        font-semibold
                        text-muted
                        mb-1
                      "
                    >
                      AI 분석
                    </p>

                    <p
                      className="
                        text-sm
                        text-ink
                        leading-relaxed
                      "
                    >
                      {item.vlmDescription}
                    </p>

                  </div>

                )}


                {/* =========================================
                    위반 규정
                ========================================= */}

                {item.violatedRegulation && (

                  <div
                    className="
                      mb-3
                    "
                  >

                    <p
                      className="
                        text-xs
                        font-semibold
                        text-muted
                        mb-1
                      "
                    >
                      관련 법령
                    </p>

                    <p
                      className="
                        text-sm
                        text-ink
                        leading-relaxed
                      "
                    >
                      {item.violatedRegulation}
                    </p>

                  </div>

                )}


                {/* =========================================
                    조치 방법
                ========================================= */}

                {item.actionGuide && (

                  <div
                    className="
                      mt-3
                      p-3
                      bg-white/70
                      rounded-md
                    "
                  >

                    <p
                      className="
                        text-xs
                        font-semibold
                        text-muted
                        mb-1
                      "
                    >
                      권장 조치
                    </p>

                    <p
                      className="
                        text-sm
                        text-ink
                        leading-relaxed
                      "
                    >
                      {item.actionGuide}
                    </p>

                  </div>

                )}


                {/* =========================================
                    상세 보기
                ========================================= */}

                {item.id && (

                  <Link
                    to={
                      `/history/${item.id}`
                    }
                    className="
                      inline-block
                      mt-3
                      text-xs
                      font-semibold
                      text-accent
                      no-underline
                    "
                  >
                    상세 보기 →
                  </Link>

                )}

              </div>

            );
          }
        )

      )}

    </div>
  );
}


export default ResultList;