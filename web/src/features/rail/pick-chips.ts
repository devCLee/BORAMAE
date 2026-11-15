import type { Chip } from "@/contracts/types";
import type { Point } from "@/state/types";
import chipsJson from "@content/chips.json";

type Season = Chip["seasons"][number];
type Box = { south: number; north: number; west: number; east: number };

/** The example chips of step 1 (FR-30). lint-content checks the file. */
export const CHIPS = chipsJson as Chip[];

const CHIP_COUNT = 6;
const DEFAULT_COUNTRY = "KR";
const US = "US";
/** Meteorological seasons of the Northern Hemisphere, by month 0 (January) to 11. */
const SEASON_BY_MONTH: Season[] = [
  "winter", "winter",
  "spring", "spring", "spring",
  "summer", "summer", "summer",
  "autumn", "autumn", "autumn",
  "winter",
];
// ponytail: rough boxes around the 48 states, Alaska and Hawaii; FR-30 does not define
// "country in view" (TRD Q-19). A center in none of them reads as Korea, the default.
const US_BOXES: Box[] = [
  { south: 24.5, north: 49.5, west: -125, east: -66.9 },
  { south: 51, north: 71.5, west: -170, east: -129.9 },
  { south: 18.9, north: 22.3, west: -160.3, east: -154.8 },
];

/**
 * Six chips for the country in view (the map center in the US, else Korea) and
 * the season of today's month, in the order of the table.
 */
export function pickChips(
  chips: Chip[],
  center: Point | null,
  today: Date,
): Chip[] {
  const country = center !== null && isInUs(center) ? US : DEFAULT_COUNTRY;
  const season = SEASON_BY_MONTH[today.getMonth()];
  return chips
    .filter((chip) => chip.country === country && chip.seasons.includes(season))
    .slice(0, CHIP_COUNT);
}

function isInUs({ lat, lon }: Point): boolean {
  return US_BOXES.some(
    (box) =>
      lat >= box.south && lat <= box.north && lon >= box.west && lon <= box.east,
  );
}
