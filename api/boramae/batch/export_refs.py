"""The stored trends that a bundled board or scan names by key (referenced of a case).

A node trend belongs to its board, so export-demo fails without it. A scan hit trend
only gives the hit its rate in the fallback (web/src/features/fallback/ScanLists.tsx),
so a hit trend that the store lacks is skipped with one line that names its key.
"""

import sys
from collections.abc import Callable

from boramae.batch.warm import TREND_KIND
from boramae.contracts.results_board import CaseBoard
from boramae.contracts.results_scan import ScanResult
from boramae.ports import ObjectStore
from boramae.store.results import result_path

# (kind, key) to the stored body; raises when the body is not stored.
ReadStored = Callable[[str, str], bytes]


def node_trends(board_body: bytes, read: ReadStored) -> dict[str, bytes]:
    """The stored trend of each board node with a trend key, by key."""
    return {
        node.trend_key: read(TREND_KIND, node.trend_key)
        for node in CaseBoard.model_validate_json(board_body).nodes
        if node.trend_key is not None
    }


def hit_trends(case_id: str, scan_body: bytes, store: ObjectStore) -> dict[str, bytes]:
    """The stored trend of each scan hit, by key, without the ones not stored."""
    keys = [hit.trend_key for hit in ScanResult.model_validate_json(scan_body).hits]
    bodies = {key: store.get(result_path(TREND_KIND, key)) for key in keys}
    for key in [key for key, body in bodies.items() if body is None]:
        print(
            f"export-demo: {case_id}: hit trend {key} is not stored; skipped",
            file=sys.stderr,
        )
    return {key: body for key, body in bodies.items() if body is not None}
