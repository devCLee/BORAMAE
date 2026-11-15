import type {
  CatalogInputs,
  Chip,
  DraftSpec,
  InvestigationSpec,
  LocalizedText,
  MetricSettings,
  ProposedVariable,
  SpecMetric,
} from "@/contracts/types";
import catalogInputsJson from "@content/catalog-inputs.json";

const INPUTS = (catalogInputsJson as unknown as CatalogInputs).inputs;

export interface ChipQuestion {
  text: LocalizedText;
  draft: DraftSpec;
  windowStart: number | null;
}

/**
 * The draft of a proposed variable. The parsed metric fills it when it names the
 * same variable and metric; otherwise the service fills the catalog defaults.
 */
export function toDraft(
  proposed: Pick<ProposedVariable, "var" | "metric_id">,
  spec: InvestigationSpec | null,
): DraftSpec {
  const parsed = spec?.metric;
  if (!parsed || parsed.var !== proposed.var || parsed.id !== proposed.metric_id) {
    return { var: proposed.var, metric: { id: proposed.metric_id } };
  }
  return {
    var: proposed.var,
    metric: {
      id: parsed.id,
      op: parsed.op ?? null,
      threshold: parsed.value == null ? null : String(parsed.value),
      months: parsed.months ?? null,
      season_start: parsed.season_start ?? null,
    },
  };
}

/** The question and the expected outcome of the catalog input of a chip (FR-30). */
export function toChipQuestion(chip: Chip): ChipQuestion {
  const input = INPUTS.find((item) => item.id === chip.input_id);
  if (input === undefined || !("var" in input.expected)) {
    // pick-chips.test.ts checks that every chip names an input the app can run.
    throw new Error(`Chip ${chip.input_id} names no catalog input with a spec.`);
  }
  const { var: variable, metric_id, months, threshold, op, window_start } =
    input.expected;
  return {
    text: input.text,
    draft: { var: variable, metric: { id: metric_id, months, threshold, op } },
    windowStart: window_start,
  };
}

/** What the service runs: each empty member takes the catalog default. */
export function effectiveMetric(
  metric: SpecMetric,
  defaults: MetricSettings | undefined,
): Required<Pick<MetricSettings, "threshold" | "op" | "months">> {
  return {
    threshold: metric.threshold ?? defaults?.threshold ?? null,
    op: metric.op ?? defaults?.op ?? null,
    months: metric.months ?? defaults?.months ?? null,
  };
}
