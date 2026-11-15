import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";

import { messages } from "./messages";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale;

  // ponytail: one fixed zone, so the export does not hold the zone of the build machine.
  // UTC is the day basis of the daily metrics. Use a zone per place if the UI shows local times.
  return { locale, messages: messages[locale], timeZone: "UTC" };
});
