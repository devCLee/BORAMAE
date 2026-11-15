/**
 * The API contract for the frontend (docs/BUILD_CONTRACT.md). Frozen from wave 2:
 * report a needed change.
 *
 * The records come from api.gen.ts, which `npm run gen:contracts` writes from the
 * pydantic models. Import contract types from this module, not from api.gen.ts.
 * The API records keep their snake_case fields. Only RequestMeta, which the fetch
 * layer builds, uses camelCase.
 */
import type {
  AgentAppState,
  BoardLink,
  CatalogVariable,
  DeltaMessage,
  ErrorMessage,
  FinalMessage,
  ParseRequest,
  RegistryRow,
  RequestSpec,
  ScanResult,
  SpecMetric,
  ToolCallMessage,
  ToolResultMessage,
  TrendResult,
  UserMessage,
} from "./api.gen";

export type * from "./api.gen";

export type Lang = ParseRequest["lang"];
export type Units = AgentAppState["units"];
export type ResultKind = RequestSpec["kind"];
export type Area = RequestSpec["area"];
export type Op = NonNullable<SpecMetric["op"]>;
export type ShareScale = NonNullable<CatalogVariable["share_scale"]>;
export type Verdict = NonNullable<TrendResult["verdict"]>;
export type NoVerdictReason = NonNullable<TrendResult["reason"]>;
export type MetricUsed = NonNullable<TrendResult["metric_used"]>;
export type TrendFlag = TrendResult["flags"][number];
export type ArrowLabel = NonNullable<BoardLink["label"]>;
export type RegistryStatus = RegistryRow["status"];
export type NearbyNote = NonNullable<ScanResult["nearby_note"]>;
export type ToolName = ToolCallMessage["tool"];
export type AgentClientMessage = UserMessage | ToolResultMessage;
export type AgentServerMessage =
  | DeltaMessage
  | ToolCallMessage
  | FinalMessage
  | ErrorMessage;
export type CacheStatus = "hit" | "miss";

export const HEADER_RESULT_KEY = "X-Result-Key";
export const HEADER_REQUEST_ID = "X-Request-Id";
export const HEADER_CACHE = "X-Cache";
export const HEADER_BYTES_FETCHED = "X-Bytes-Fetched";
export const HEADER_SERVER_TIMING = "Server-Timing";
/** Sent with the value "true" only when no cell center fell inside the area. */
export const HEADER_CONTAINING_CELL = "X-Containing-Cell";

/**
 * The facts of one answered request. They come from the response headers, or
 * from the demo manifest for a bundled file, and never from a result body.
 */
export interface RequestMeta {
  resultKey: string;
  /** Null for a bundled demo file, which no request log line describes. */
  requestId: string | null;
  cache: CacheStatus | null;
  bytesFetched: number | null;
  serverTiming: string | null;
  usedContainingCell: boolean;
  /** Where the same body can be read again: /r/{kind}/{key}.json or the bundled file. */
  sourceUrl: string;
}
