import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const WEB_ROOT = import.meta.dirname;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: "@content", replacement: path.join(WEB_ROOT, "../content") },
      { find: "@", replacement: path.join(WEB_ROOT, "src") },
      // jsdom has no WebGL. The exact match keeps maplibre-gl/dist/*.css on the real package.
      {
        find: /^maplibre-gl$/,
        replacement: path.join(WEB_ROOT, "src/test/mocks/maplibre-gl.ts"),
      },
    ],
  },
  test: {
    environment: "jsdom",
    // Testing Library registers its cleanup and its act environment only on global hooks.
    globals: true,
    setupFiles: ["src/test/setup.ts"],
    // next-intl imports next/navigation with no file extension, which only Vite can resolve.
    server: { deps: { inline: ["next-intl"] } },
  },
});
