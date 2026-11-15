import { afterEach, expect, test, vi } from "vitest";

import { readMapColors } from "./map-style";

const PAINTED_PIXEL = new Uint8ClampedArray([247, 247, 247, 255]);

/** Stands in for the 2D canvas, which jsdom lacks: every fill paints the same gray. */
function stubCanvas(): void {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    fillStyle: "",
    fillRect: vi.fn(),
    getImageData: () => ({ data: PAINTED_PIXEL }),
  } as unknown as CanvasRenderingContext2D);
}

afterEach(() => {
  document.documentElement.style.removeProperty("--muted");
  vi.restoreAllMocks();
});

test("should give the map an rgb color for a lab role value", () => {
  document.documentElement.style.setProperty("--muted", "lab(96.52% 0 0)");
  stubCanvas();

  expect(readMapColors().sea).toBe("rgb(247, 247, 247)");
});

test("should leave an unset role empty", () => {
  expect(readMapColors().sea).toBe("");
});
