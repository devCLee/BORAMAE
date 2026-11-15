import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { expect, test } from "vitest";

import { VerdictChip, type ChipVerdict } from "@/components/VerdictChip";
import { messages } from "@/i18n/messages";

const WORDS: { verdict: ChipVerdict; en: string; ko: string }[] = [
  { verdict: "significant_rise", en: "Rising, significant", ko: "유의한 상승" },
  { verdict: "significant_fall", en: "Falling, significant", ko: "유의한 하강" },
  { verdict: "not_yet", en: "Not yet significant", ko: "아직 유의하지 않음" },
  { verdict: "no_trend", en: "No trend detected", ko: "감지된 추세 없음" },
  { verdict: "record_too_short", en: "Record too short", ko: "기록이 너무 짧음" },
];

function renderChip(verdict: ChipVerdict, locale: "en" | "ko" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <VerdictChip verdict={verdict} />
    </NextIntlClientProvider>,
  );
}

test.each(WORDS)("should show the word for $verdict", ({ verdict, en }) => {
  renderChip(verdict);

  expect(screen.getByText(en)).toBeInTheDocument();
});

test.each(WORDS)("should show the Korean word for $verdict", ({ verdict, ko }) => {
  renderChip(verdict, "ko");

  expect(screen.getByText(ko)).toBeInTheDocument();
});

test.each(WORDS)("should show an icon for $verdict", ({ verdict, en }) => {
  renderChip(verdict);

  expect(screen.getByText(en).querySelector("svg")).toBeInTheDocument();
});

test.each(WORDS)("should hide the icon of $verdict from screen readers", ({ verdict, en }) => {
  renderChip(verdict);

  expect(screen.getByText(en).querySelector("svg")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
});
