"""Ports between the services and their I/O. Frozen from wave 2: report a change."""

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from boramae.engine.types import CellSeries, GridDef

Freq = Literal["monthly", "daily"]


class SeriesReader(Protocol):
    """Reads POWER cells. Months are 'YYYY-MM' and both window ends are inclusive.

    A cell is (lat_index, lon_index) on the grid. Box index ranges are half-open,
    as Python slices. Every read failure raises errors.PowerUnavailable.
    """

    def grid(self) -> GridDef: ...

    def variables(self, freq: Freq) -> Mapping[str, str]:
        """Variable names of the store, each with its unit."""
        ...

    def read_cells(
        self,
        var: str,
        freq: Freq,
        cells: Sequence[tuple[int, int]],
        start: str,
        end: str,
    ) -> CellSeries: ...

    def read_box(
        self,
        var: str,
        freq: Freq,
        lat_i0: int,
        lat_i1: int,
        lon_i0: int,
        lon_i1: int,
        start: str,
        end: str,
    ) -> CellSeries: ...

    def last_valid_month(self, freq: Freq) -> str:
        """The pinned month, 'YYYY-MM'. No read returns a step after it."""
        ...


class ObjectStore(Protocol):
    """Holds result and content files by path."""

    def get(self, path: str) -> bytes | None:
        """The stored body, or None when no file exists at the path."""
        ...

    def create_once(self, path: str, body: bytes) -> bool:
        """Write only if no file exists. True when this call created the file."""
        ...

    def put(self, path: str, body: bytes) -> None:
        """Write or replace. Only for files that may change, such as the catalog."""
        ...
