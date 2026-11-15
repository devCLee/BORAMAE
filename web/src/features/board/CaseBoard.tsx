"use client";

import { RotateCwIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useId, useRef, useSyncExternalStore } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { IS_LIVE_BOARD_ON } from "@/config/flags";
import type { BoardNode, CaseBoard as Board } from "@/contracts/types";
import { useCaseBoard, useCatalog, useTrend } from "@/hooks/queries";
import { runAnalysis } from "@/state/run-analysis";
import { useAppStore } from "@/state/store";

import { BoardArrow } from "./BoardArrow";
import { type NumSource, SideTitle } from "./board-parts";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * The case board of a significant verdict (FR-18, TR-F-026): up to 3 drivers and 3
 * responses around the focus. Every label comes from the result; the browser tests
 * nothing. With the live-board flag off, only a demo case shows its bundled board
 * (PRD "Hour-18 cut rules"), and the verdict card above stays in every state.
 */
export function CaseBoard() {
  const t = useTranslations("board");
  const titleId = useId();
  // A control that leaves the screen, such as the retry, hands its focus to the board.
  const rootRef = useRef<HTMLElement>(null);
  const isBundled = useAppStore((state) => state.fetchSource === "fixture");

  return (
    <section
      data-testid="slot-board"
      ref={rootRef}
      tabIndex={-1}
      aria-labelledby={titleId}
      className="@container flex flex-col gap-3"
    >
      <h3 id={titleId} className="text-sm font-medium">
        {t("title")}
      </h3>
      {IS_LIVE_BOARD_ON || isBundled ? (
        <BoardAnswer onFocusBoard={() => rootRef.current?.focus()} />
      ) : (
        <p className="text-sm text-muted-foreground">{t("live_off")}</p>
      )}
    </section>
  );
}

function BoardAnswer({ onFocusBoard }: { onFocusBoard: () => void }) {
  const t = useTranslations("board");
  const board = useCaseBoard();
  const focus = useTrend().data;
  useEffect(() => {
    // runAnalysis never rejects; the query of the panel shows the outcome.
    void runAnalysis("caseboard");
  }, []);

  if (board.data === undefined && board.fetchStatus === "fetching") {
    return (
      <div role="status" aria-label={t("loading")} className="flex flex-col gap-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    );
  }
  if (board.isError) {
    return (
      <div className="flex flex-col items-center">
        <EmptyState messageKey={board.error.code} />
        <Button
          variant="outline"
          className="min-h-11"
          onClick={() => {
            onFocusBoard();
            void board.refetch();
          }}
        >
          <RotateCwIcon aria-hidden />
          {t("retry")}
        </Button>
      </div>
    );
  }
  if (board.data === undefined) {
    return null;
  }
  const { body, meta } = board.data;
  if (body.board_id === null) {
    return <p className="text-sm text-muted-foreground">{t("no_board")}</p>;
  }
  // ponytail: the link numbers carry the provenance of the focus trend, because a board
  // result has none of its own and its links run on the same cells and window. Give
  // BoardLink a provenance if the drawer must name the link test and both series.
  const linkSource: NumSource | null = focus
    ? { provenance: focus.body.provenance, footprint: focus.body.footprint, meta }
    : null;

  return <BoardLayout board={body} linkSource={linkSource} />;
}

/**
 * Drivers, the focus, then responses. They stack in the narrow case panel and on a
 * phone, and stand side by side, drivers left, once the board has the width.
 */
function BoardLayout({ board, linkSource }: { board: Board; linkSource: NumSource | null }) {
  const t = useTranslations("board");
  const catalog = useCatalog().data;
  const isAnimated = !useIsMotionReduced();
  const focusTitleId = useId();
  const arrowsOf = (role: BoardNode["role"]) => (
    <ArrowGroup role={role}>
      {board.nodes
        .filter((node) => node.role === role)
        .map((node) => (
          <BoardArrow
            key={node.row.id}
            node={node}
            order={board.nodes.indexOf(node)}
            isAnimated={isAnimated}
            catalog={catalog}
            linkSource={linkSource}
          />
        ))}
    </ArrowGroup>
  );

  return (
    <>
      <p className="text-sm text-muted-foreground">{t("intro")}</p>
      {/* ponytail: three columns from a 42rem board; the 20 to 24rem case panel stacks. */}
      <div className="grid gap-4 @2xl:grid-cols-3">
        {arrowsOf("driver")}
        <div
          role="group"
          aria-labelledby={focusTitleId}
          className="flex flex-col justify-center gap-1 self-center rounded-lg border-2 p-3 text-sm"
        >
          <span id={focusTitleId} className="text-xs text-muted-foreground">
            {t("focus")}
          </span>
          <p className="font-medium">
            <SideTitle side={board.spec} catalog={catalog} />
          </p>
        </div>
        {arrowsOf("response")}
      </div>
    </>
  );
}

function ArrowGroup({ role, children }: { role: BoardNode["role"]; children: ReactNode[] }) {
  const t = useTranslations("board");
  const titleId = useId();

  return (
    <div className="flex flex-col gap-2">
      <h4 id={titleId} className="text-xs font-medium text-muted-foreground">
        {t(`groups.${role}`)}
      </h4>
      {children.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("none")}</p>
      ) : (
        <ul aria-labelledby={titleId} className="flex flex-col gap-2">
          {children}
        </ul>
      )}
    </div>
  );
}

function useIsMotionReduced(): boolean {
  return useSyncExternalStore(
    subscribeToMotion,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    // The static build draws no motion.
    () => true,
  );
}

function subscribeToMotion(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
