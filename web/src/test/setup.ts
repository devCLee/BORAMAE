/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

import { Map as MockMap, Marker as MockMarker } from "@/test/mocks/maplibre-gl";

// jsdom has neither. Radix needs ResizeObserver (Slider, Tooltip), and a reduced-motion check needs matchMedia.
// Plain assignment and not vi.stubGlobal, so vi.unstubAllGlobals in a test keeps both.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
globalThis.matchMedia = (query: string): MediaQueryList => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
  dispatchEvent: () => false,
});

beforeEach(() => {
  MockMap.instances.length = 0;
  MockMarker.instances.length = 0;
});
