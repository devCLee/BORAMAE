import { useTranslations } from "next-intl";

/** A data unit as the units messages label it, or as the catalog writes it. */
export function useUnitLabel(): (unit: string) => string {
  const t = useTranslations("units");
  return (unit) => {
    const labelKey = `label.${unit}`;
    return t.has(labelKey) ? t(labelKey) : unit;
  };
}
