"use client";

import { XIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

import { ProvenanceDetails } from "./ProvenanceDetails";
import {
  closeProvenance,
  focusOpener,
  useProvenanceTarget,
} from "./provenance-state";

/** The one provenance drawer (FR-26). Num opens it through provenance-state. */
export function ProvenanceDrawer() {
  const t = useTranslations("provenance");
  const target = useProvenanceTarget();

  return (
    <div data-testid="slot-provenance">
      <Sheet
        open={target !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            closeProvenance();
          }
        }}
      >
        {target && (
          <SheetContent
            showCloseButton={false}
            className="overflow-y-auto"
            onCloseAutoFocus={(event) => {
              // Radix would focus a trigger, and this drawer has none.
              event.preventDefault();
              focusOpener();
            }}
          >
            <SheetHeader className="pr-14">
              <SheetTitle>{t("title")}</SheetTitle>
              <SheetDescription>{t("description")}</SheetDescription>
            </SheetHeader>
            <ProvenanceDetails target={target} />
            <SheetClose asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("close")}
                className="absolute top-2 right-2 size-11"
              >
                <XIcon aria-hidden />
              </Button>
            </SheetClose>
          </SheetContent>
        )}
      </Sheet>
    </div>
  );
}
