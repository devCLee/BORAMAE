"""POWER reader: the anonymous Zarr stores, a chunk cache and byte accounting (DES-007).

This module holds the only data-source address of the API. It reads the Zarr stores
and never the POWER API (TR-D-001).
"""

import asyncio
import re
import threading
from collections import OrderedDict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import xarray as xr
from zarr.abc.store import ByteRequest
from zarr.core.buffer import Buffer, BufferPrototype
from zarr.storage import FsspecStore, WrapperStore

from boramae.config import Settings, load_settings
from boramae.engine.series import present_months
from boramae.engine.types import CellSeries, Footprint, GridDef
from boramae.errors import PowerUnavailable
from boramae.ports import Freq

STORE_URL = (
    "https://nasa-power.s3.us-west-2.amazonaws.com"
    "/merra2/temporal/power_merra2_{freq}_temporal_utc.zarr"
)
GRID_DLAT = 0.5
GRID_DLON = 0.625
PROBE_VARIABLE = "T2M"
PROBE_CELL = (255, 491)  # Seoul: the pinned month is read from this cell
# The decimal digits that a variable holds. Each data variable of both stores declares
# them, and its fixed-scale filter has the scale 10**digits (metadata of 2026-11-15).
DIGITS_ATTRIBUTE = "significant_digits"
# The group attributes 'id' and 'version' name the dataset of a store, such as
# 'power_merra2_daily_temporal_utc.zarr' and 'POWER Version 10.0.0' (2026-11-15).
STORE_ID_SUFFIX = ".zarr"
DOTTED_VERSION = re.compile(r"\d+(?:\.\d+)+")


@dataclass
class _Ledger:
    """What one read needed and fetched: the stored size of each chunk, by key."""

    chunk_bytes: dict[str, int] = field(default_factory=dict)
    fetched_bytes: int = 0


# zarr runs a store call on its own I/O thread, with a copy of the caller's context.
# The ledger of a read therefore reaches the store without a lock around the read.
_LEDGER: ContextVar[_Ledger | None] = ContextVar("power_read_ledger", default=None)


class _ChunkCache:
    """An LRU of stored chunks. An entry is the stored bytes, so its length is the
    stored size of the chunk.

    Only the zarr I/O thread calls it, so it needs no lock.
    """

    # ponytail: the limit counts stored (compressed) bytes, and every read decodes its
    # chunks again. Cache decoded blocks if the decode time shows up in a profile.
    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes
        self._chunks: OrderedDict[str, Buffer] = OrderedDict()
        self._bytes = 0

    def get(self, key: str) -> Buffer | None:
        if key in self._chunks:
            self._chunks.move_to_end(key)
        return self._chunks.get(key)

    def put(self, key: str, chunk: Buffer) -> None:
        self._bytes += len(chunk) - len(self._chunks.pop(key, b""))
        self._chunks[key] = chunk
        while self._bytes > self._max_bytes:
            _, evicted = self._chunks.popitem(last=False)
            self._bytes -= len(evicted)


class _MeteredStore(WrapperStore[FsspecStore]):
    """Adds the read timeout to a store and, inside a read, the cache and the ledger."""

    def __init__(
        self, store: FsspecStore, cache: _ChunkCache, timeout_s: float
    ) -> None:
        super().__init__(store)
        self._cache = cache
        self._timeout_s = timeout_s

    async def get(
        self,
        key: str,
        prototype: BufferPrototype,
        byte_range: ByteRequest | None = None,
    ) -> Buffer | None:
        ledger = _LEDGER.get()
        if ledger is None or byte_range is not None:
            return await self._fetch(key, prototype, byte_range)
        cache_key = f"{self._store.path}/{key}"
        chunk = self._cache.get(cache_key)
        if chunk is None:
            chunk = await self._fetch(key, prototype, None)
            if chunk is None:
                return None
            self._cache.put(cache_key, chunk)
            ledger.fetched_bytes += len(chunk)
        ledger.chunk_bytes[key] = len(chunk)
        return chunk

    async def _fetch(
        self, key: str, prototype: BufferPrototype, byte_range: ByteRequest | None
    ) -> Buffer | None:
        return await asyncio.wait_for(
            self._store.get(key, prototype, byte_range), self._timeout_s
        )


class PowerReader:
    """Reads the monthly and daily POWER stores (ports.SeriesReader).

    A store opens on first use and stays open, so a failed open fails one call and
    not the process. Times are datetime64[D]. A read returns no step after the
    pinned month of its store.
    """

    def __init__(self, settings: Settings) -> None:
        self._timeout_s = settings.power_chunk_timeout_s
        self._cache = _ChunkCache(settings.chunk_cache_bytes)
        self._datasets: dict[Freq, xr.Dataset] = {}
        self._pinned: dict[Freq, str] = {}
        self._open_lock = threading.Lock()

    def grid(self) -> GridDef:
        dataset = self._dataset("monthly")
        lat, lon = dataset["lat"].values, dataset["lon"].values
        return GridDef(
            float(lat[0]), GRID_DLAT, lat.size, float(lon[0]), GRID_DLON, lon.size
        )

    def variables(self, freq: Freq) -> Mapping[str, str]:
        data_vars = self._dataset(freq).data_vars
        return {str(name): array.attrs["units"] for name, array in data_vars.items()}

    def read_cells(
        self,
        var: str,
        freq: Freq,
        cells: Sequence[tuple[int, int]],
        start: str,
        end: str,
    ) -> CellSeries:
        """Read values[time, cell] for the months start to end, both inclusive.

        The footprint is the count and the stored size of the chunks that hold the
        cells and the window, whether the cache held them or not. A chunk that the
        store lacks reads as NaN and is not counted. fetched_bytes is the stored size
        of the chunks that this call took from the store.
        """
        months = self._steps(freq).astype("datetime64[M]")
        last = min(end, self.last_valid_month(freq))
        first_step = int(np.searchsorted(months, np.datetime64(start, "M"), "left"))
        end_step = int(np.searchsorted(months, np.datetime64(last, "M"), "right"))
        steps = slice(first_step, max(first_step, end_step))
        return self._read(var, freq, np.asarray(cells).reshape(-1, 2), steps)

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
        """Read every cell of a half-open index box. The latitude index runs first."""
        cells = [(i, j) for i in range(lat_i0, lat_i1) for j in range(lon_i0, lon_i1)]
        return self.read_cells(var, freq, cells, start, end)

    def last_valid_month(self, freq: Freq) -> str:
        """The last month whose every step holds a value at the probe cell.

        The time axis runs past the data, so the month comes from the values. It is
        found once and then kept, so a recompute reads the same window.
        """
        if freq not in self._pinned:
            self._pinned[freq] = self._find_last_valid_month(freq)
        return self._pinned[freq]

    def _find_last_valid_month(self, freq: Freq) -> str:
        whole_axis = slice(0, self._steps(freq).size)
        probe = self._read(PROBE_VARIABLE, freq, np.array([PROBE_CELL]), whole_axis)
        months = present_months(probe.times, probe.values[:, 0], freq)
        if months.size == 0:
            raise PowerUnavailable(
                f"the {freq} store holds no complete month of {PROBE_VARIABLE}"
            )
        return str(months[-1])

    def _steps(self, freq: Freq) -> npt.NDArray[np.datetime64]:
        times = self._dataset(freq)["time"].values
        # ponytail: no document fixes the stamp of a monthly step. The store stamps the
        # last day of the month; this reader returns the first day, as FakeReader does.
        unit = "datetime64[M]" if freq == "monthly" else "datetime64[D]"
        return times.astype(unit).astype("datetime64[D]")

    def _read(
        self, var: str, freq: Freq, cells: npt.NDArray[np.intp], steps: slice
    ) -> CellSeries:
        dataset = self._dataset(freq)
        array = dataset[var]
        chunks = array.encoding["preferred_chunks"]
        lat_blocks = cells[:, 0] // chunks["lat"]
        block_ids = lat_blocks * dataset.sizes["lon"] + cells[:, 1] // chunks["lon"]
        values = np.empty((steps.stop - steps.start, len(cells)))
        ledger = _Ledger()
        context = _LEDGER.set(ledger)
        try:
            # ponytail: the blocks load one after another; zarr fetches the chunks of
            # one block together. Load the blocks together if a wide daily area is slow.
            for block_id in np.unique(block_ids):
                picked = np.flatnonzero(block_ids == block_id)
                lat_i, lon_i = cells[picked].T
                lat_i0, lon_i0 = lat_i.min(), lon_i.min()
                box = array.isel(
                    time=steps,
                    lat=slice(lat_i0, lat_i.max() + 1),
                    lon=slice(lon_i0, lon_i.max() + 1),
                ).transpose("time", "lat", "lon")
                with _store_errors(f"read of {var} from the {freq} store"):
                    loaded = box.values
                values[:, picked] = loaded[:, lat_i - lat_i0, lon_i - lon_i0]
        finally:
            _LEDGER.reset(context)
        digits = array.attrs.get(DIGITS_ATTRIBUTE)
        if digits is not None:
            # The store holds a whole number of 10**-digits steps, and its filter
            # decodes in float32: a stored 0.10 arrives as 0.0999755859375 and fails
            # a test against 0.1. Rounding in float64 gives the stored value back.
            np.round(values, digits, out=values)
        footprint = Footprint(len(ledger.chunk_bytes), sum(ledger.chunk_bytes.values()))
        return CellSeries(
            self._steps(freq)[steps], values, footprint, ledger.fetched_bytes
        )

    def _dataset(self, freq: Freq) -> xr.Dataset:
        # ponytail: one lock for both stores, so a slow open of one delays a call on
        # the other. Use a lock per store if that wait shows up.
        with self._open_lock:
            if freq not in self._datasets:
                self._datasets[freq] = self._open(freq)
            return self._datasets[freq]

    def _open(self, freq: Freq) -> xr.Dataset:
        with _store_errors(f"open of the {freq} store"):
            remote = FsspecStore.from_url(STORE_URL.format(freq=freq), read_only=True)
            store = _MeteredStore(remote, self._cache, self._timeout_s)
            dataset = xr.open_zarr(
                store,
                consolidated=True,
                zarr_format=2,
                chunks=None,
                decode_timedelta=False,
            )
        lat_steps, lon_steps = np.diff(dataset["lat"]), np.diff(dataset["lon"])
        if not (
            np.allclose(lat_steps, GRID_DLAT) and np.allclose(lon_steps, GRID_DLON)
        ):
            raise PowerUnavailable(
                f"the {freq} store is not on the ascending "
                f"{GRID_DLAT} x {GRID_DLON} degree grid"
            )
        return dataset


def read_store_identity(freq: Freq) -> tuple[str, str]:
    """The dataset ID and version of a store, from its consolidated group attributes.

    It opens the store as a read does, so a failed open raises PowerUnavailable.
    """
    # ponytail: a second open of the store beside the reader of build-catalog, one
    # more metadata fetch per catalog build. Share the open dataset if that ever counts.
    return store_identity(PowerReader(load_settings())._open(freq).attrs)


def store_identity(attributes: Mapping[str, object]) -> tuple[str, str]:
    """The store attributes 'id' and 'version' as (dataset ID, dataset version).

    Raises ValueError for a version text with no dotted version number.
    """
    version_text = str(attributes["version"])
    found = DOTTED_VERSION.search(version_text)
    if found is None:
        raise ValueError(
            f"the store version {version_text!r} holds no dotted version number"
        )
    return str(attributes["id"]).removesuffix(STORE_ID_SUFFIX), found.group()


@contextmanager
def _store_errors(action: str) -> Iterator[None]:
    """Turn every failure of a store call, a timeout included, into PowerUnavailable."""
    try:
        yield
    except Exception as exc:
        raise PowerUnavailable(f"POWER {action} failed: {exc!r}") from exc
