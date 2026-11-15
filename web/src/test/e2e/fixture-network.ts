/**
 * The network of the end-to-end tests: fetch stubbed with the sample fixtures. It
 * answers as the service does on a live walk, or as the static host of the demo
 * bundle does on a demo walk, and it records every request.
 */
import { API_BASE } from "@/config/flags";
import {
  type DemoCase,
  HEADER_RESULT_KEY,
  type ManifestCase,
  type ManifestFile,
  type ParseProposal,
  type RequestSpec,
  type ScanResult,
  type TrendResult,
} from "@/contracts/types";
import { DEMO_CASES } from "@/features/demo/demo-content";
import {
  jsonResponse,
  problemResponse,
  serve,
  type StubCall,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { encodeSpec } from "@/lib/spec-codec";
import {
  caseBoard,
  catalog,
  parseInput1En,
  parseInput1Ko,
  scanNote,
  trendSignificant,
} from "@/test/fixtures";

const RESULT_KEY = "0123456789abcdef".repeat(2);

/**
 * The service, path by path. Every stored trend, of a board node or of a scan hit,
 * is the significant sample. Every other path gets a 404.
 */
export function serveService(
  proposal: ParseProposal,
  trend: TrendResult,
  scan: ScanResult,
): StubCall[] {
  const answers: [path: string, body: unknown][] = [
    ["/meta/catalog.json", catalog],
    ["/api/v1/parse", proposal],
    ["/api/v1/trend?", trend],
    ["/api/v1/caseboard?", caseBoard],
    ["/api/v1/scan?", scan],
    ["/r/trend/", trendSignificant],
  ];
  return stubFetch(({ url }) => {
    const body = answers.find(([path]) => url.startsWith(API_BASE + path))?.[1];
    return body === undefined
      ? problemResponse(404, "not_found")
      : jsonResponse(body, { headers: { [HEADER_RESULT_KEY]: RESULT_KEY } });
  });
}

/**
 * The demo bundle in the shape that export-demo writes from content/demo/cases.json,
 * with sample files. Every other request gets a 404, as on a static host.
 */
export function serveBundle(trend: TrendResult): StubCall[] {
  const files = DEMO_CASES.flatMap(({ id }): [string, unknown][] => [
    [`/demo/${id}/parse.en.json`, parseInput1En],
    [`/demo/${id}/parse.ko.json`, parseInput1Ko],
    [`/demo/${id}/trend.json`, trend],
    [`/demo/${id}/caseboard.json`, caseBoard],
    [`/demo/${id}/scan.json`, scanNote],
  ]);
  return stubFetch(
    serve({
      ...Object.fromEntries(files),
      "/demo/manifest.json": {
        catalog: "catalog.json",
        cases: DEMO_CASES.map(toManifestCase),
      },
      "/demo/catalog.json": catalog,
    }),
  );
}

/** export-demo encodes the same specs in the service, and lint:demo checks that the scripts send them. */
function toManifestCase({ id, specs }: DemoCase): ManifestCase {
  const kinds = Object.entries(specs).flatMap(
    ([kind, spec]: [string, RequestSpec | null]): [string, ManifestFile][] =>
      spec === null
        ? []
        : [[kind, { file: `${id}/${kind}.json`, key: RESULT_KEY, s: encodeSpec(spec) }]],
  );
  return {
    case_id: id,
    parse: { en: `${id}/parse.en.json`, ko: `${id}/parse.ko.json` },
    kinds: Object.fromEntries(kinds),
    referenced: {},
    answers: { en: null, ko: null },
  };
}
