"""Test doubles for every API test: FakeReader, DictStore and make_client."""

import threading
import zlib
from collections.abc import Callable, Iterable, Mapping, Sequence

import numpy as np
import numpy.typing as npt
from fastapi.testclient import TestClient

from boramae import deps
from boramae.constants import VARIABLE_IDS
from boramae.engine.types import CellSeries, Footprint, GridDef
from boramae.errors import PowerUnavailable
from boramae.main import create_app
from boramae.ports import Freq, ObjectStore, SeriesReader
from boramae.services.parser_llm import ModelParser

POWER_GRID = GridDef(
    lat0=-90.0, dlat=0.5, n_lat=361, lon0=-180.0, dlon=0.625, n_lon=576
)
DEFAULT_LAST_MONTH = "2026-09"
# ponytail: the fake knows no POWER units; every variable reports this one.
FAKE_UNIT = "1"
# A fake stored size of one step; the real footprint counts the stored chunks.
STORED_STEP_BYTES = 4
FREQS: tuple[Freq, ...] = ("monthly", "daily")
# Both axes run to 2029-12 like the padded stores, and the daily one starts a day
# early. Times are datetime64[D], a monthly step on its first day, as PowerReader.
AXES = {
    "monthly": np.arange(np.datetime64("1981-01"), np.datetime64("2030-01")).astype(
        "datetime64[D]"
    ),
    "daily": np.arange(np.datetime64("1980-12-31"), np.datetime64("2030-01-01")),
}

Cell = tuple[int, int]
ValuesFn = Callable[[str, Freq, npt.NDArray[np.datetime64], Cell], npt.ArrayLike]


class FakeReader:
    """ports.SeriesReader over the POWER grid with values seeded per variable and cell.

    Like PowerReader, no read returns a step after the pinned month, last_month.
    values_fn(var, freq, times, cell) gives exact values for the returned times;
    fail makes every data call raise PowerUnavailable; missing_vars are absent from
    the store and reading one raises KeyError. The footprint of a read depends only
    on the read; a cell's first read fetches its stored bytes and a repeat fetches 0.
    Box columns run latitude first, as a C-order flatten of [lat, lon].
    """

    def __init__(
        self,
        last_month: str = DEFAULT_LAST_MONTH,
        values_fn: ValuesFn | None = None,
        fail: bool = False,
        missing_vars: Iterable[str] = (),
    ) -> None:
        self.last_month = last_month
        self.values_fn = values_fn
        self.fail = fail
        self.missing_vars = frozenset(missing_vars)
        self.read_count = 0
        self._fetched: set[tuple[str, str, Cell]] = set()

    def grid(self) -> GridDef:
        self._raise_if_failing()
        return POWER_GRID

    def variables(self, freq: Freq) -> Mapping[str, str]:
        self._raise_if_failing()
        return {var: FAKE_UNIT for var in VARIABLE_IDS if var not in self.missing_vars}

    def last_valid_month(self, freq: Freq) -> str:
        self._raise_if_failing()
        return self.last_month

    def read_cells(
        self,
        var: str,
        freq: Freq,
        cells: Sequence[tuple[int, int]],
        start: str,
        end: str,
    ) -> CellSeries:
        self.read_count += 1
        self._raise_if_failing()
        if var in self.missing_vars:
            raise KeyError(var)
        cells = [(int(lat_i), int(lon_i)) for lat_i, lon_i in cells]
        axis = AXES[freq]
        months = axis.astype("datetime64[M]")
        last = min(np.datetime64(end, "M"), np.datetime64(self.last_month, "M"))
        in_window = (months >= np.datetime64(start, "M")) & (months <= last)
        times = axis[in_window]
        values = np.empty((times.size, len(cells)))
        for column, cell in enumerate(cells):
            values[:, column] = self._cell_values(var, freq, cell, in_window, times)
        return CellSeries(
            times=times,
            values=values,
            footprint=Footprint(len(set(cells)), len(set(cells)) * _cell_bytes(freq)),
            fetched_bytes=self._fetch(var, freq, cells),
        )

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
    ) -> CellSeries:
        cells = [
            (lat_i, lon_i)
            for lat_i in range(lat_i0, lat_i1)
            for lon_i in range(lon_i0, lon_i1)
        ]
        return self.read_cells(var, freq, cells, start, end)

    def _raise_if_failing(self) -> None:
        if self.fail:
            raise PowerUnavailable("FakeReader is set to fail")

    def _cell_values(
        self,
        var: str,
        freq: Freq,
        cell: Cell,
        in_window: npt.NDArray[np.bool_],
        times: npt.NDArray[np.datetime64],
    ) -> npt.NDArray[np.float64]:
        if self.values_fn is not None:
            return np.asarray(self.values_fn(var, freq, times, cell), dtype=np.float64)
        seed = [zlib.crc32(var.encode()), FREQS.index(freq), *cell]
        whole_axis = np.random.default_rng(seed).standard_normal(AXES[freq].size)
        return whole_axis[in_window]

    def _fetch(self, var: str, freq: Freq, cells: Sequence[Cell]) -> int:
        new = {(var, freq, cell) for cell in cells} - self._fetched
        self._fetched |= new
        return len(new) * _cell_bytes(freq)


def _cell_bytes(freq: Freq) -> int:
    return AXES[freq].size * STORED_STEP_BYTES


class DictStore:
    """ports.ObjectStore in memory; files holds every stored body by its path."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def get(self, path: str) -> bytes | None:
        return self.files.get(path)

    def create_once(self, path: str, body: bytes) -> bool:
        with self._lock:
            if path in self.files:
                return False
            self.files[path] = body
            return True

    def put(self, path: str, body: bytes) -> None:
        self.files[path] = body


def make_client(
    reader: SeriesReader | None = None,
    store: ObjectStore | None = None,
    catalog: object | None = None,
    model_parser: ModelParser | None = None,
) -> TestClient:
    """A TestClient of create_app() with its collaborators replaced.

    The reader defaults to a FakeReader, the store to a DictStore and the model
    parser to None (the LLM is off). With no catalog, get_catalog loads the catalog
    from the store as in production.
    """
    app = create_app()
    reader = FakeReader() if reader is None else reader
    store = DictStore() if store is None else store
    app.dependency_overrides[deps.get_reader] = lambda: reader
    app.dependency_overrides[deps.get_store] = lambda: store
    app.dependency_overrides[deps.get_model_parser] = lambda: model_parser
    if catalog is not None:
        app.dependency_overrides[deps.get_catalog] = lambda: catalog
    return TestClient(app)
