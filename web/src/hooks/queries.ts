"use client";

/**
 * The query hooks (HookName in state/types.ts). Each one reads its request from
 * the client store. TanStack Query never retries here: the fetch layer owns the
 * retry rule (DES-003). An error is a FetchError, and its code is a key of the
 * "errors" messages.
 */
import {
  skipToken,
  useMutation,
  type UseMutationResult,
  useQuery,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useEffect } from "react";

import type { Catalog, ParseProposal } from "@/contracts/types";
import {
  type Answer,
  fetchCatalog,
  type FetchError,
  fetchParse,
  type ResultByKind,
} from "@/lib/fetch-layer";
import { encodeRequest, sendAnalysis } from "@/state/run-analysis";
import { actions, getState, useAppStore } from "@/state/store";
import type { PanelKind } from "@/state/types";

export function useCatalog(): UseQueryResult<Catalog, FetchError> {
  const source = useAppStore((state) => state.fetchSource);
  return useQuery<Catalog, FetchError>({
    // The source is part of the key, so a switch of the source reads the catalog again.
    queryKey: ["catalog", source],
    queryFn: () => fetchCatalog(source),
    retry: false,
    // ponytail: one read for each tab. A catalog that fell back to the bundle
    // stays until a reload; lower staleTime if the app must pick up the service again.
    staleTime: Infinity,
  });
}

/**
 * Sends a question to parse: mutate(text). The language, the session ID and the
 * running demo case come from the store. A second question aborts the first.
 */
export function useParse(): UseMutationResult<ParseProposal, FetchError, string> {
  return useMutation<ParseProposal, FetchError, string>({
    mutationFn: (text) => {
      const { fetchSource, lang, sessionId, demo } = getState();
      return fetchParse(
        fetchSource,
        { text, lang, session_id: sessionId },
        demo?.caseId ?? null,
      );
    },
    retry: false,
  });
}

export function useTrend(): AnalysisQuery<"trend"> {
  return useAnalysis("trend");
}

export function useCaseBoard(): AnalysisQuery<"caseboard"> {
  return useAnalysis("caseboard");
}

export function useScan(): AnalysisQuery<"scan"> {
  return useAnalysis("scan");
}

/** data.body is the result, and data.meta holds the facts of its request. */
export type AnalysisQuery<K extends PanelKind> = UseQueryResult<
  Answer<ResultByKind[K]>,
  FetchError
>;

/**
 * The result of one panel. It asks only while the panel is open and the spec is
 * confirmed (TR-F-004), and it asks again when the request changes, as after a
 * new time window (TR-F-016).
 */
function useAnalysis<K extends PanelKind>(kind: K): AnalysisQuery<K> {
  const source = useAppStore((state) => state.fetchSource);
  const s = useAppStore((state) =>
    state.openPanels.includes(kind) ? encodeRequest(state, kind) : null,
  );
  const query = useQuery<Answer<ResultByKind[K]>, FetchError>({
    queryKey: ["analysis", kind, source, s],
    queryFn: s === null ? skipToken : () => sendAnalysis(kind, s),
    retry: false,
    // ponytail: a stored result never changes, so one read for each request. A
    // "latest" window keeps its month until a reload, and POWER adds one a month.
    staleTime: Infinity,
  });
  const meta = query.data?.meta ?? null;
  useEffect(() => {
    // The store names the result that the panel shows, also for one from the query cache.
    actions.setRequestMeta(kind, meta);
  }, [kind, meta]);
  return query;
}
