// ponytail: hand-written to match api/boramae/contracts/news.py. Move to the generated
// contracts once export.py lists the news models.
export interface NewsResult {
  items: {
    title: string;
    source: string;
    published: string;
    url: string;
    feed: "google_news_en" | "google_news_ko" | "gdelt";
  }[];
  feeds: {
    feed: string;
    status: "ok" | "empty" | "timeout" | "error" | "skipped";
    count: number;
    coverage: string | null;
  }[];
}

export interface NewsParams {
  q: string;
  start: string;
  end: string;
}

const MAX_QUERY_CHARS = 80;
// The characters that GET /api/v1/context/news rejects in q.
const REJECTED_CHARS = /[^\p{L}\p{N} .,'-]/gu;

/**
 * The news request for a case: the variable name and the place name, January 1
 * of the window start year, and the last day of the window end month, capped at today.
 */
export function toNewsParams(
  variableName: string,
  placeName: string | null,
  [startYear, end]: [number, string],
  today: Date,
): NewsParams {
  const q = [variableName, placeName ?? ""]
    .join(" ")
    .replace(REJECTED_CHARS, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX_QUERY_CHARS)
    .trim();
  const [endYear, endMonth] = end.split("-").map(Number);
  // Day 0 of the next month is the last day of this one.
  const monthEnd = new Date(Date.UTC(endYear, endMonth, 0)).toISOString().slice(0, 10);
  const todayIso = today.toISOString().slice(0, 10);
  return {
    q,
    start: `${startYear}-01-01`,
    end: monthEnd < todayIso ? monthEnd : todayIso,
  };
}
