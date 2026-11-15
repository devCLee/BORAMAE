import { setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/shell/AppShell";
import { Providers } from "@/components/shell/Providers";

export default async function LocalePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <Providers>
      <AppShell />
    </Providers>
  );
}
