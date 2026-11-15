import { setRequestLocale } from "next-intl/server";

import { MethodsPage } from "@/features/methods/MethodsPage";

export default async function MethodsRoute({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <MethodsPage />;
}
