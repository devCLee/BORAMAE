import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { stubFetch } from "@/lib/fetch-layer.stub";
import { resetStore } from "@/state/store";
import { setWorkerUrl } from "@/test/mocks/maplibre-gl";

import { renderMap, serveApi } from "./map-test-kit";

beforeEach(() => {
  resetStore();
  stubFetch(serveApi());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should start the map worker from the bundled file", () => {
  renderMap();

  expect(setWorkerUrl).toHaveBeenCalledWith("/basemap/maplibre-gl-worker.mjs");
});
