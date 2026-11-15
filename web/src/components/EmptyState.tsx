"use client";

import { CircleAlertIcon, RotateCwIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import type errorMessages from "@/messages/en/errors.json";

// ponytail: zoom_in_or_pin and not_in_offline_demo come from the plan; timeout, network,
// unavailable and server are working values for the typed errors of the fetch layer.
export type ErrorMessageKey = keyof (typeof errorMessages)["messages"];

interface EmptyStateProps {
  messageKey: ErrorMessageKey;
  /** Without it the state offers no retry, as for zoom_in_or_pin. */
  onRetry?: () => void;
}

export function EmptyState({ messageKey, onRetry }: EmptyStateProps) {
  const t = useTranslations("errors");

  return (
    <div
      role="status"
      className="flex flex-col items-center gap-3 p-6 text-center text-sm text-muted-foreground"
    >
      <CircleAlertIcon aria-hidden className="size-6" />
      <p>{t(`messages.${messageKey}`)}</p>
      {onRetry && (
        <Button variant="outline" className="min-h-11" onClick={onRetry}>
          <RotateCwIcon aria-hidden />
          {t("retry")}
        </Button>
      )}
    </div>
  );
}
