import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "ko"],
  defaultLocale: "en",
  // The static export has no middleware that reads a locale cookie, so the router writes none.
  localeCookie: false,
});
