import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { Slider } from "@/components/ui/slider";

const FIRST_YEAR = 1981;
const LAST_YEAR = 2025;

test("should render one thumb for each value of a two-value Slider", () => {
  render(<Slider defaultValue={[FIRST_YEAR, LAST_YEAR]} />);

  expect(screen.getAllByRole("slider")).toHaveLength(2);
});

test("should report no reduced-motion preference by default", () => {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");

  expect(query.matches).toBe(false);
});

test("should keep ResizeObserver when a test removes its stubbed globals", () => {
  vi.unstubAllGlobals();

  expect(typeof ResizeObserver).toBe("function");
});

test("should keep matchMedia when a test removes its stubbed globals", () => {
  vi.unstubAllGlobals();

  expect(typeof window.matchMedia).toBe("function");
});
