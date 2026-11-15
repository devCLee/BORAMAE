const SCHOLAR_SEARCH = "https://scholar.google.com/scholar";

/**
 * The Google Scholar search for a case (FR-21): the variable name, the place name
 * when one exists, and the years of the window. Scholar has no API, so the app only
 * links to it and never queries it.
 */
export function toScholarUrl(
  variableName: string,
  placeName: string | null,
  [startYear, end]: [number, string],
): string {
  const params = new URLSearchParams({
    q: placeName === null ? variableName : `${variableName} ${placeName}`,
    as_ylo: String(startYear),
    as_yhi: end.slice(0, 4),
  });
  return `${SCHOLAR_SEARCH}?${params}`;
}
