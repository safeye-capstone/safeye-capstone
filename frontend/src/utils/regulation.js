// 법령명 뒤에 붙는 (고용노동부령)(제00450호)(20260302) 같은 메타데이터 제거
const META_PATTERN = /\((?:[^()]*령|제\d+호|\d{8})\)/g;

const articleNo = (article) => Number(article.match(/제(\d+)조/)?.[1] ?? 0);

/**
 * 위반 규정 문자열을 법령별 조문 목록으로 변환합니다.
 * "규칙(고용노동부령)(제00450호)(20260302) 제43조(...) / 규칙(...) 제42조(...)"
 * → [{ law: "규칙", articles: ["제42조(...)", "제43조(...)"] }]
 */
export function parseRegulations(text) {
  if (!text) return [];

  const groups = new Map();

  text
    .split(/\s+\/\s+/)
    .map((item) => item.replace(META_PATTERN, "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .forEach((item) => {
      const match = item.match(/^(.*?)\s*(제\d+조.*)$/);
      const law = match ? match[1] : "";
      const article = match ? match[2] : item;

      if (!groups.has(law)) groups.set(law, new Set());
      groups.get(law).add(article);
    });

  return [...groups].map(([law, articles]) => ({
    law,
    articles: [...articles].sort((a, b) => articleNo(a) - articleNo(b)),
  }));
}
