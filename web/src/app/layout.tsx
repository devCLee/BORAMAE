import type { ReactNode } from "react";

// The html element needs the language of the route, so the root page and the
// locale layout each render their own html and body.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
