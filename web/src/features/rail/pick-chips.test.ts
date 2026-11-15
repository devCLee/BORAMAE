import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { CatalogInputs } from "@/contracts/types";
import { actions, getState, resetStore } from "@/state/store";
import catalogInputsJson from "@content/catalog-inputs.json";

import { CHIPS, pickChips } from "./pick-chips";
import { QUESTION_EN, renderRail, serveApi } from "./rail-test-utils";

const INPUTS = (catalogInputsJson as unknown as CatalogInputs).inputs;
const SEOUL = { lat: 37.5665, lon: 126.978 };
const PHOENIX = { lat: 33.4484, lon: -112.074 };
const ANCHORAGE = { lat: 61.2181, lon: -149.9003 };
const AUTUMN_DAY = new Date(2026, 10, 15);

/** One day in each season of the Northern Hemisphere, and each country in view. */
const CASES = [
  { season: "winter", today: new Date(2026, 0, 15), country: "KR", center: SEOUL },
  { season: "spring", today: new Date(2026, 3, 15), country: "KR", center: SEOUL },
  { season: "summer", today: new Date(2026, 6, 15), country: "KR", center: SEOUL },
  { season: "autumn", today: new Date(2026, 9, 15), country: "KR", center: SEOUL },
  { season: "winter", today: new Date(2026, 0, 15), country: "US", center: PHOENIX },
  { season: "spring", today: new Date(2026, 3, 15), country: "US", center: PHOENIX },
  { season: "summer", today: new Date(2026, 6, 15), country: "US", center: PHOENIX },
  { season: "autumn", today: new Date(2026, 9, 15), country: "US", center: PHOENIX },
];

beforeEach(() => {
  resetStore();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(AUTUMN_DAY);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function inputOf(inputId: number) {
  return INPUTS.find((input) => input.id === inputId);
}

test.each(CASES)(
  "should return six chips in $season over $country",
  ({ center, today }) => {
    expect(pickChips(CHIPS, center, today)).toHaveLength(6);
  },
);

test.each(CASES)(
  "should span at least four intent types in $season over $country",
  ({ center, today }) => {
    const intents = new Set(
      pickChips(CHIPS, center, today).map((chip) => chip.intent),
    );

    expect(intents.size).toBeGreaterThanOrEqual(4);
  },
);

test.each(CASES)(
  "should pick only chips of the season in $season over $country",
  ({ season, center, today }) => {
    const seasons = pickChips(CHIPS, center, today).map((chip) => chip.seasons);

    expect(seasons).toEqual(Array(6).fill(expect.arrayContaining([season])));
  },
);

test.each(CASES)(
  "should pick only places of the country in $season over $country",
  ({ country, center, today }) => {
    const countries = pickChips(CHIPS, center, today).map(
      (chip) => chip.country,
    );

    expect(countries).toEqual(Array(6).fill(country));
  },
);

test("should pick Korean places when the map shows no view yet", () => {
  const countries = pickChips(CHIPS, null, new Date(2026, 10, 15)).map(
    (chip) => chip.country,
  );

  expect(countries).toEqual(Array(6).fill("KR"));
});

test("should pick US places when the map centers on Alaska", () => {
  const countries = pickChips(CHIPS, ANCHORAGE, new Date(2026, 10, 15)).map(
    (chip) => chip.country,
  );

  expect(countries).toEqual(Array(6).fill("US"));
});

test("should take the season from the month of today", () => {
  const seasons = pickChips(CHIPS, SEOUL, new Date(2026, 11, 1)).map(
    (chip) => chip.seasons,
  );

  expect(seasons).toEqual(Array(6).fill(expect.arrayContaining(["winter"])));
});

test.each(CHIPS)(
  "should point chip $input_id at a catalog input that the app can run",
  ({ input_id }) => {
    expect(inputOf(input_id)?.expected).toMatchObject({ supported: true });
  },
);

test.each(CHIPS)(
  "should give chip $input_id the intent of its catalog input",
  ({ input_id, intent }) => {
    expect(inputOf(input_id)?.intent).toBe(intent);
  },
);

test.each(CHIPS)(
  "should give chip $input_id the country of its catalog place",
  ({ input_id, country }) => {
    expect(inputOf(input_id)?.place?.country).toBe(country);
  },
);

test("should show six example chips", () => {
  actions.chooseDoor("guided");
  renderRail();

  const chips = screen.getByRole("list", { name: "Example questions" });

  expect(within(chips).getAllByRole("button")).toHaveLength(6);
});

test("should fill the draft from the expected outcome of a chip", async () => {
  serveApi();
  actions.chooseDoor("guided");
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: QUESTION_EN }));

  expect(getState().draftSpec).toEqual({
    var: "PRECSNO",
    metric: { id: "first_date", months: null, threshold: "0.1", op: ">=" },
  });
});

test("should read the spec back after a chip tap", async () => {
  serveApi();
  actions.chooseDoor("guided");
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: QUESTION_EN }));

  expect(
    await screen.findByText(
      "The current map view: First date of Snowfall, at or above 0.1 mm/day, 1981 onward?",
    ),
  ).toBeInTheDocument();
});

test("should tap a chip with the keyboard", async () => {
  serveApi();
  actions.chooseDoor("guided");
  renderRail();
  screen.getByRole("button", { name: QUESTION_EN }).focus();

  await userEvent.keyboard("{Enter}");

  await waitFor(() => expect(getState().draftSpec?.var).toBe("PRECSNO"));
});
