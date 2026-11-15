import { LanguageGate } from "@/components/shell/LanguageGate";

import { fontClassName } from "./fonts";

import "./globals.css";

// The gate shows both languages, and its Korean parts carry lang="ko".
export default function RootPage() {
  return (
    <html lang="en" className={fontClassName}>
      <body>
        <main className="grid min-h-dvh place-items-center p-6">
          <LanguageGate />
        </main>
      </body>
    </html>
  );
}
