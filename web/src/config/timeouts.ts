// ponytail: no document fixes these values (TRD Q-23), so each one is a placeholder
// from the build plan. Set them here once the latency runs give numbers.

/** How long the browser waits for one answer, for each class of path. */
export const TIMEOUT_MS = {
  parse: 8_000,
  /** A stored result by its key, and a bundled demo file. */
  stored: 10_000,
  analysis: 60_000,
  meta: 10_000,
  /** The news path reads three feeds, each with a 5 s socket timeout on the service. */
  context: 30_000,
} as const;

// ponytail: fixed waits, and the Retry-After header of a 503 answer is not read. The
// service sends 5 s today. Read the header here if the service starts to tune it.
/** The wait before each retry. The length of the list is the retry limit (TDD Flow B). */
export const RETRY_DELAYS_MS = [1_000, 2_000, 4_000] as const;
