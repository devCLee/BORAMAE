/**
 * The shared setup of the map tests: the map rendered with the real store, the
 * real query hooks and a fetch stub, and the mock map that maplibre-gl gives.
 */
import { act, render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import type { TrendResult } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import {
  jsonResponse,
  problemResponse,
  type Respond,
} from "@/lib/fetch-layer.stub";
import { catalog, scanNearby, trendSignificant } from "@/test/fixtures";
import { Map as MockMap } from "@/test/mocks/maplibre-gl";

import { MapView } from "./MapView";

export const SEOUL = { lat: 37.5665, lon: 126.978 };

const RESULT_HEADERS = { headers: { "X-Result-Key": "k" } };

/** Each path of the service answers with its sample. A test can replace the trend answer. */
export function serveApi(
  trend: TrendResult | Response = trendSignificant,
): Respond {
  const answers: [string, () => Response][] = [
    [`${API_BASE}/meta/catalog.json`, () => jsonResponse(catalog)],
    [
      `${API_BASE}/api/v1/trend?`,
      () =>
        trend instanceof Response ? trend : jsonResponse(trend, RESULT_HEADERS),
    ],
    [`${API_BASE}/api/v1/scan?`, () => jsonResponse(scanNearby, RESULT_HEADERS)],
  ];
  return ({ url }) =>
    answers.find(([prefix]) => url.startsWith(prefix))?.[1]() ??
    problemResponse(404, "not_found");
}

export function renderMap(): MockMap {
  render(
    <Providers>
      <NextIntlClientProvider locale="en" messages={messages.en} timeZone="UTC">
        <MapView />
      </NextIntlClientProvider>
    </Providers>,
  );
  return MockMap.instances[0];
}

export function renderLoadedMap(): MockMap {
  const map = renderMap();
  act(() => {
    map.fire("load");
  });
  return map;
}

/** The data that the last setData call gave the source. */
export function lastData(map: MockMap, sourceId: string): unknown {
  return map.getSource(sourceId)?.setData.mock.lastCall?.[0];
}
