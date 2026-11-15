import { useSyncExternalStore } from "react";

import type { Footprint, Provenance, RequestMeta } from "@/contracts/types";

/** What the drawer shows: the record of one number, and the facts of its request. */
export interface ProvenanceTarget {
  provenance: Provenance;
  footprint: Footprint | null;
  /** Null when no request answered the number, such as a bundled demo file (Q-018). */
  meta: RequestMeta | null;
}

let target: ProvenanceTarget | null = null;
// The drawer has no trigger of its own, so the element that opened it gets the focus back.
let opener: HTMLElement | null = null;
const listeners = new Set<() => void>();

export function openProvenance(
  next: ProvenanceTarget,
  from: HTMLElement | null,
): void {
  target = next;
  opener = from;
  notify();
}

export function closeProvenance(): void {
  target = null;
  notify();
}

export function focusOpener(): void {
  opener?.focus();
}

export function useProvenanceTarget(): ProvenanceTarget | null {
  return useSyncExternalStore(subscribe, getTarget, getServerTarget);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getTarget(): ProvenanceTarget | null {
  return target;
}

function getServerTarget(): null {
  return null;
}

function notify(): void {
  for (const listener of listeners) {
    listener();
  }
}
