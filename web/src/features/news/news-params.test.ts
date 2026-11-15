import { expect, test } from "vitest";

import { toNewsParams } from "./news-params";

const TODAY = new Date("2026-11-15T12:00:00Z");

test("should drop the characters that the news API rejects from the query", () => {
  const { q } = toNewsParams("Hot days (>35 °C)", "Seoul/서울", [1981, "2020-12"], TODAY);

  expect(q).toBe("Hot days 35 C Seoul서울");
});

test("should cut the query to 80 characters", () => {
  const { q } = toNewsParams("a".repeat(100), null, [1981, "2020-12"], TODAY);

  expect(q).toHaveLength(80);
});

test("should start on January 1 of the window start year", () => {
  const { start } = toNewsParams("Snowfall", null, [1991, "2020-12"], TODAY);

  expect(start).toBe("1991-01-01");
});

test("should end on the last day of the window end month", () => {
  const { end } = toNewsParams("Snowfall", null, [1991, "2024-02"], TODAY);

  expect(end).toBe("2024-02-29");
});

test("should cap the end at today when the end month is the current month", () => {
  const { end } = toNewsParams("Snowfall", null, [1991, "2026-11"], TODAY);

  expect(end).toBe("2026-11-15");
});
