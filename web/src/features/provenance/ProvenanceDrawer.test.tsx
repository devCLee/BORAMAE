import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { beforeEach, expect, test } from "vitest";

import { Num } from "@/components/Num";
import type { RequestMeta } from "@/contracts/types";
import { ProvenanceDrawer } from "@/features/provenance/ProvenanceDrawer";
import {
  closeProvenance,
  openProvenance,
  type ProvenanceTarget,
} from "@/features/provenance/provenance-state";
import { messages } from "@/i18n/messages";
import { trendNoTrend, trendSignificant } from "@/test/fixtures";

const LIVE_META: RequestMeta = {
  resultKey: "b5bae5463e95eff888bca78a896bf62a",
  requestId: "req-7f3a9c",
  cache: "hit",
  bytesFetched: 1234567,
  serverTiming: "read;dur=40, total;dur=52",
  usedContainingCell: false,
  sourceUrl: "/r/trend/b5bae5463e95eff888bca78a896bf62a.json",
};
const BUNDLED_META: RequestMeta = {
  ...LIVE_META,
  requestId: null,
  cache: null,
  bytesFetched: null,
  serverTiming: null,
  sourceUrl: "/demo/first-snow-seoul/trend.json",
};
const DAILY_TARGET: ProvenanceTarget = {
  provenance: trendSignificant.provenance,
  footprint: trendSignificant.footprint,
  meta: null,
};
const MONTHLY_TARGET: ProvenanceTarget = {
  provenance: trendNoTrend.provenance,
  footprint: trendNoTrend.footprint,
  meta: null,
};

function renderIn(ui: ReactNode, locale: "en" | "ko" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      {ui}
    </NextIntlClientProvider>,
  );
}

function openDrawer(target: ProvenanceTarget, locale: "en" | "ko" = "en") {
  renderIn(<ProvenanceDrawer />, locale);
  act(() => openProvenance(target, null));
  return screen.getByRole("dialog");
}

beforeEach(() => {
  closeProvenance();
});

test("should keep the slot element while closed", () => {
  renderIn(<ProvenanceDrawer />);

  expect(screen.getByTestId("slot-provenance")).toBeInTheDocument();
});

test("should keep the slot element while open", () => {
  openDrawer(DAILY_TARGET);

  expect(screen.getByTestId("slot-provenance")).toBeInTheDocument();
});

test.each([
  { field: "dataset ID", text: "power_merra2_daily_temporal_utc" },
  { field: "dataset version", text: "Version 2026-09" },
  {
    field: "access path",
    text: "s3://nasa-power/merra2/temporal/power_merra2_daily_temporal_utc.zarr",
  },
  { field: "period", text: "Jan 1981 to Sep 2026" },
  { field: "cells used", text: "1 grid cell" },
  { field: "cell index", text: "[255, 491]" },
  {
    field: "method",
    text: "Sen slope and the Mann–Kendall test with the lag-1 Hamed–Rao correction",
  },
  { field: "data moved", text: "4 chunks of the POWER store (30.4 MB)" },
  { field: "compute location", text: "us-west-2" },
  { field: "day basis", text: "Days run from 00:00 to 24:00 UTC." },
])("should show the $field", ({ text }) => {
  const drawer = openDrawer(DAILY_TARGET);

  expect(drawer).toHaveTextContent(text);
});

test("should leave out the day basis of a monthly source", () => {
  const drawer = openDrawer(MONTHLY_TARGET);

  expect(drawer).not.toHaveTextContent("Day basis");
});

test("should name the observing-system changes of model data", () => {
  const drawer = openDrawer(DAILY_TARGET);

  expect(drawer).toHaveTextContent(
    "part of a long-term change can come from changes in the observing system",
  );
});

test("should label model data as model, not observation", () => {
  const drawer = openDrawer(DAILY_TARGET);

  expect(drawer).toHaveTextContent("Model data, not observation");
});

test.each([
  { fact: "bytes fetched", text: "This request read 1,234,567 bytes from POWER." },
  { fact: "cache status", text: "Cache: hit, a stored result" },
  { fact: "request ID", text: "Request ID req-7f3a9c" },
])("should show the $fact as the request meta holds it", ({ text }) => {
  const drawer = openDrawer({ ...DAILY_TARGET, meta: LIVE_META });

  expect(drawer).toHaveTextContent(text);
});

test("should show a cache miss as the request meta holds it", () => {
  const drawer = openDrawer({
    ...DAILY_TARGET,
    meta: { ...LIVE_META, cache: "miss" },
  });

  expect(drawer).toHaveTextContent("Cache: miss, computed for this request");
});

test("should show the file footprint without request meta", () => {
  const drawer = openDrawer(DAILY_TARGET);

  expect(drawer).toHaveTextContent("4 chunks of the POWER store");
});

test.each([
  { fact: "bytes fetched", text: "from POWER." },
  { fact: "cache status", text: "Cache:" },
  { fact: "request ID", text: "Request ID" },
])("should leave out the $fact without request meta", ({ text }) => {
  const drawer = openDrawer(DAILY_TARGET);

  expect(drawer).not.toHaveTextContent(text);
});

test("should leave out the request facts of a bundled demo file", () => {
  const drawer = openDrawer({ ...DAILY_TARGET, meta: BUNDLED_META });

  expect(drawer).not.toHaveTextContent("Request ID");
});

test("should point the download link at the source URL of the meta", () => {
  openDrawer({ ...DAILY_TARGET, meta: LIVE_META });

  expect(
    screen.getByRole("link", { name: "Download the analysis JSON" }),
  ).toHaveAttribute("href", LIVE_META.sourceUrl);
});

test("should offer no download without request meta", () => {
  openDrawer(DAILY_TARGET);

  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

test("should show the drawer in Korean", () => {
  openDrawer(DAILY_TARGET, "ko");

  expect(
    screen.getByRole("dialog", { name: "이 숫자의 출처" }),
  ).toBeInTheDocument();
});

test("should close from the named close control", async () => {
  openDrawer(DAILY_TARGET);

  await userEvent.click(screen.getByRole("button", { name: "Close" }));

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("should close on Escape", async () => {
  openDrawer(DAILY_TARGET);

  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("should return focus to the info button that opened it", async () => {
  renderIn(
    <>
      <Num value={1.5} provenance={DAILY_TARGET.provenance} />
      <ProvenanceDrawer />
    </>,
  );
  const infoButton = screen.getByRole("button", { name: "Source of 1.5" });
  await userEvent.click(infoButton);

  await userEvent.click(screen.getByRole("button", { name: "Close" }));

  await waitFor(() => expect(infoButton).toHaveFocus());
});
