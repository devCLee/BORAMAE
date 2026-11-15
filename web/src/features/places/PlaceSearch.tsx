"use client";

import { useLocale, useTranslations } from "next-intl";
import { type KeyboardEvent, useId, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Lang, Place } from "@/contracts/types";
import { actions } from "@/state/store";

import { matchPlaces } from "./match-place";

const NO_OPTION = -1;

/**
 * A search field with a list of gazetteer places (TR-F-008), as an ARIA combobox.
 * A chosen place sets the pin and flies the map there. With no match the field
 * says so, and a map click still pins any point.
 */
export function PlaceSearch() {
  const t = useTranslations("places.search");
  const tKind = useTranslations("places.kind");
  const lang = useLocale() as Lang;
  const fieldId = useId();
  const listId = useId();
  const fieldRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [active, setActive] = useState(NO_OPTION);
  const matches = matchPlaces(query);
  const isListShown = isOpen && matches.length > 0;
  const isNoMatch = isOpen && query.trim() !== "" && matches.length === 0;

  function choose(place: Place) {
    const point = { lat: place.lat, lon: place.lon };
    actions.setPin(point, "user");
    actions.setMapTarget({ center: point, zoom: null });
    setQuery(place.name[lang]);
    setIsOpen(false);
    setActive(NO_OPTION);
    fieldRef.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    const count = matches.length;
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && count > 0) {
      event.preventDefault();
      const isDown = event.key === "ArrowDown";
      setIsOpen(true);
      // The first press enters the list at its top or its bottom; then it wraps.
      setActive((index) =>
        index === NO_OPTION
          ? isDown ? 0 : count - 1
          : (index + (isDown ? 1 : -1) + count) % count,
      );
    } else if (event.key === "Enter") {
      event.preventDefault();
      const place = matches[active] ?? matches[0];
      if (place !== undefined) {
        choose(place);
      }
    } else if (event.key === "Escape") {
      setIsOpen(false);
      setActive(NO_OPTION);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={fieldId}>{t("label")}</Label>
      <Input
        ref={fieldRef}
        id={fieldId}
        role="combobox"
        aria-expanded={isListShown}
        aria-controls={isListShown ? listId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={
          isListShown && active !== NO_OPTION ? `${listId}-${active}` : undefined
        }
        autoComplete="off"
        value={query}
        placeholder={t("placeholder")}
        onChange={(event) => {
          setQuery(event.target.value);
          setIsOpen(true);
          setActive(NO_OPTION);
        }}
        onKeyDown={handleKeyDown}
        className="min-h-11"
      />
      {isListShown && (
        <ul
          id={listId}
          role="listbox"
          aria-label={t("results")}
          className="flex max-h-64 flex-col overflow-y-auto rounded-md border bg-background py-1"
        >
          {matches.map((place, index) => (
            <li
              key={place.id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              // The field keeps the focus, so the list stays a part of it.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(place)}
              className="flex min-h-11 cursor-pointer items-center justify-between gap-2 px-3 text-sm aria-selected:bg-accent hover:bg-accent"
            >
              <span>{place.name[lang]}</span>
              <span className="text-xs text-muted-foreground">
                {tKind(place.kind === "city" ? "city" : "region")} · {place.country}
              </span>
            </li>
          ))}
        </ul>
      )}
      {isNoMatch && (
        <p role="status" className="text-sm">
          {t("no_match", { query: query.trim() })}
        </p>
      )}
    </div>
  );
}
