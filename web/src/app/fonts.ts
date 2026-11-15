import localFont from "next/font/local";

// DEC-004: the font ships inside the static export, so no page asks a font server.
// Pretendard covers Hangul and Latin and is licensed under OFL-1.1 (node_modules/pretendard/dist/LICENSE.txt).
// ponytail: the one variable file is about 2 MB. Switch to the package's woff2-dynamic-subset files if the first phone load is too slow.
const pretendard = localFont({
  src: "../../node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2",
  weight: "45 920",
  display: "swap",
  variable: "--font-pretendard",
  fallback: ["system-ui", "Apple SD Gothic Neo", "Malgun Gothic", "sans-serif"],
});

export const fontClassName = pretendard.variable;
