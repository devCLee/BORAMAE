import { readFileSync } from "node:fs";
import path from "node:path";

const CSS_FILE = path.join(import.meta.dirname, "../src/app/globals.css");

// WCAG 2.2 AA: SC 1.4.3 for text, SC 1.4.11 for icons and component edges.
const MIN_RATIO = { text: 4.5, icon: 3 };

const VERDICT_ROLES = [
  "trend-rise",
  "trend-fall",
  "not-yet",
  "no-trend",
  "too-short",
  "ai-badge",
];
const ROLE_SURFACES = ["background", "card", "muted"];

const PAIRS = [
  ...VERDICT_ROLES.flatMap((role) =>
    ROLE_SURFACES.map((surface) => ({ color: role, surface, kind: "text" })),
  ),
  { color: "foreground", surface: "background", kind: "text" },
  { color: "card-foreground", surface: "card", kind: "text" },
  { color: "popover-foreground", surface: "popover", kind: "text" },
  { color: "primary-foreground", surface: "primary", kind: "text" },
  { color: "secondary-foreground", surface: "secondary", kind: "text" },
  { color: "accent-foreground", surface: "accent", kind: "text" },
  { color: "muted-foreground", surface: "background", kind: "text" },
  { color: "muted-foreground", surface: "muted", kind: "text" },
  { color: "destructive", surface: "background", kind: "text" },
  { color: "coverage-muted", surface: "background", kind: "icon" },
  { color: "input", surface: "background", kind: "icon" },
  { color: "primary", surface: "background", kind: "icon" },
  { color: "ring", surface: "background", kind: "icon" },
  // The shadcn controls draw their focus ring at half opacity (ring-ring/50).
  { color: "ring", surface: "background", kind: "icon", alpha: 0.5 },
];

const OKLCH_PATTERN = /^oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)$/;

function main() {
  const colors = readRootColors(readFileSync(CSS_FILE, "utf8"));
  const results = PAIRS.map((pair) => checkPair(pair, colors));

  for (const { pair, ratio, isPass } of results) {
    const alpha = pair.alpha === undefined ? "" : ` at ${pair.alpha * 100}%`;
    process.stdout.write(
      `${isPass ? "PASS" : "FAIL"} ${pair.kind} ${pair.color}${alpha} on ${pair.surface}: ` +
        `${ratio.toFixed(2)} (min ${MIN_RATIO[pair.kind]})\n`,
    );
  }
  const failures = results.filter((result) => !result.isPass).length;
  process.stdout.write(
    `check:contrast checked ${results.length} pairs and found ${failures} failures\n`,
  );
  process.exitCode = failures > 0 ? 1 : 0;
}

function readRootColors(css) {
  const rootBlock = css.match(/:root\s*\{([^}]*)\}/);
  if (!rootBlock) {
    throw new Error(`no :root block in ${CSS_FILE}`);
  }
  const colors = {};
  for (const [, name, value] of rootBlock[1].matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) {
    colors[name] = value.trim();
  }
  return colors;
}

function checkPair(pair, colors) {
  const surface = toSrgb(colors, pair.surface);
  const color = compose(toSrgb(colors, pair.color), surface, pair.alpha ?? 1);
  const ratio = contrastRatio(luminance(color), luminance(surface));
  return { pair, ratio, isPass: ratio >= MIN_RATIO[pair.kind] };
}

function toSrgb(colors, name) {
  const value = colors[name];
  const match = value?.match(OKLCH_PATTERN);
  if (!match) {
    throw new Error(`--${name} is "${value}", and this script reads only oklch(L C H)`);
  }
  return oklchToSrgb(...match.slice(1).map(Number));
}

// Björn Ottosson's OKLab to linear sRGB matrices, then the sRGB transfer curve.
function oklchToSrgb(lightness, chroma, hueDegrees) {
  const hue = (hueDegrees * Math.PI) / 180;
  const a = chroma * Math.cos(hue);
  const b = chroma * Math.sin(hue);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const linear = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return linear.map((channel) => encode(Math.min(1, Math.max(0, channel))));
}

// Browsers blend a translucent color over its surface in encoded sRGB.
function compose(color, surface, alpha) {
  return color.map((channel, i) => alpha * channel + (1 - alpha) * surface[i]);
}

function luminance([r, g, b]) {
  return 0.2126 * decode(r) + 0.7152 * decode(g) + 0.0722 * decode(b);
}

function contrastRatio(first, second) {
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

function encode(linear) {
  return linear <= 0.0031308 ? 12.92 * linear : 1.055 * linear ** (1 / 2.4) - 0.055;
}

function decode(encoded) {
  return encoded <= 0.04045 ? encoded / 12.92 : ((encoded + 0.055) / 1.055) ** 2.4;
}

main();
