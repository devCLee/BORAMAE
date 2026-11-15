/**
 * Typed sample records for frontend tests. Import a sample from this module, not
 * from its JSON file.
 *
 * The export command of the API writes the JSON files and checks each one against
 * its pydantic model. TypeScript gives a JSON import wide types (a verdict becomes
 * string and a cell index number[]), so a plain cast to the record type does not
 * compile. Each sample is cast once here.
 */
import type {
  CaseBoard,
  Catalog,
  DemoManifest,
  ParseProposal,
  ScanResult,
  ToolResultMessage,
  TrendResult,
  UserMessage,
} from "@/contracts/types";

import agentToolResultJson from "./agent.tool-result.sample.json";
import agentUserJson from "./agent.user.sample.json";
import caseBoardJson from "./caseboard.sample.json";
import catalogJson from "./catalog.sample.json";
import manifestJson from "./manifest.sample.json";
import parseInput1EnJson from "./parse.input-1.en.sample.json";
import parseInput1KoJson from "./parse.input-1.ko.sample.json";
import scanNearbyJson from "./scan.nearby.sample.json";
import scanNoteJson from "./scan.note.sample.json";
import trendNoDataJson from "./trend.no-data.sample.json";
import trendNoTrendJson from "./trend.no-trend.sample.json";
import trendNotYetJson from "./trend.not-yet.sample.json";
import trendSignificantJson from "./trend.significant.sample.json";
import trendTooShortJson from "./trend.too-short.sample.json";
import trendZeroInsideJson from "./trend.zero-inside.sample.json";

export const catalog = catalogJson as unknown as Catalog;
export const parseInput1Ko = parseInput1KoJson as unknown as ParseProposal;
export const parseInput1En = parseInput1EnJson as unknown as ParseProposal;
export const trendSignificant = trendSignificantJson as unknown as TrendResult;
export const trendNotYet = trendNotYetJson as unknown as TrendResult;
export const trendZeroInside = trendZeroInsideJson as unknown as TrendResult;
export const trendNoTrend = trendNoTrendJson as unknown as TrendResult;
export const trendTooShort = trendTooShortJson as unknown as TrendResult;
export const trendNoData = trendNoDataJson as unknown as TrendResult;
export const caseBoard = caseBoardJson as unknown as CaseBoard;
export const scanNearby = scanNearbyJson as unknown as ScanResult;
export const scanNote = scanNoteJson as unknown as ScanResult;
export const agentUser = agentUserJson as unknown as UserMessage;
export const agentToolResult = agentToolResultJson as unknown as ToolResultMessage;
export const manifest = manifestJson as unknown as DemoManifest;
