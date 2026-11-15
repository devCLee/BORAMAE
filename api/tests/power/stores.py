"""Tiny Zarr v2 stores on the POWER grid, for the reader tests.

Each store mirrors the layout of the real ones: a consolidated Zarr v2 group with the
arrays time, lat, lon and T2M[time, lat, lon], a time axis that runs past the data, and
NaN as the fill value. Only the chunks of one block are written, so a store stays small.
Inside the block T2M = (1000 * lat_i + lon_i) * 100 + step.

The daily store also holds PRECSNO as the real stores hold every data variable: float32
behind a fixed-scale filter (scale 100, offset 1000), with the attribute
significant_digits. Inside the block PRECSNO = (step % 20) / 100, so step 10 holds 0.10,
which the filter decodes to 0.0999755859375.
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
import zarr
from numcodecs import FixedScaleOffset

N_LAT = 361
N_LON = 576
LAT_BLOCK = slice(250, 275)
LON_BLOCK = slice(485, 515)
MONTHLY_CHUNKS = (36, 30, 30)
DAILY_CHUNKS = (50, 15, 15)
MONTHLY_VALID_STEPS = 30  # 1981-01 to 1983-06, on an axis that runs to 1983-12
DAILY_VALID_STEPS = 61  # 1980-12-31 to 1981-03-01, on an axis that runs to 1981-04-30
SNOW_VALID_STEPS = 45  # 1980-12-31 to 1981-02-13; later days are missing
SNOW_DIGITS = 2
ONE_DAY = np.timedelta64(1, "D")
ONE_MONTH = np.timedelta64(1, "M")


def write_monthly_store(path: Path, dlat: float = 0.5) -> None:
    """Month-end steps, as in the real monthly store. Values end in 1983-06."""
    months = np.arange("1981-01", "1984-01", dtype="datetime64[M]")
    month_ends = (months + ONE_MONTH).astype("datetime64[D]") - ONE_DAY
    _write_store(path, month_ends, MONTHLY_CHUNKS, MONTHLY_VALID_STEPS, dlat)


def write_daily_store(path: Path) -> None:
    """Steps from 1980-12-31. March 1981 holds one valid day and the rest is padding."""
    days = np.arange("1980-12-31", "1981-05-01", dtype="datetime64[D]")
    _write_store(path, days, DAILY_CHUNKS, DAILY_VALID_STEPS, dlat=0.5)
    _add_precsno(path, days.size)


def _add_precsno(path: Path, n_steps: int) -> None:
    root = zarr.open_group(str(path), mode="r+", zarr_format=2)
    scale = 10**SNOW_DIGITS
    precsno = root.create_array(
        "PRECSNO",
        shape=(n_steps, N_LAT, N_LON),
        chunks=DAILY_CHUNKS,
        dtype="f4",
        filters=[FixedScaleOffset(offset=1000, scale=scale, dtype="<f4", astype="<f4")],
        fill_value=np.nan,
        attributes={
            "units": "mm/day",
            "significant_digits": SNOW_DIGITS,
            "_ARRAY_DIMENSIONS": ["time", "lat", "lon"],
        },
    )
    step, lat_i, lon_i = np.ogrid[:SNOW_VALID_STEPS, LAT_BLOCK, LON_BLOCK]
    block = np.broadcast_to(step % 20 / scale, (step.size, lat_i.size, lon_i.size))
    precsno[:SNOW_VALID_STEPS, LAT_BLOCK, LON_BLOCK] = block
    zarr.consolidate_metadata(str(path), zarr_format=2)


def _write_store(
    path: Path,
    dates: npt.NDArray[np.datetime64],
    chunks: tuple[int, int, int],
    n_valid: int,
    dlat: float,
) -> None:
    root = zarr.open_group(str(path), mode="w", zarr_format=2)
    time_attributes = {
        "units": f"days since {dates[0]} 00:00:00",
        "calendar": "proleptic_gregorian",
    }
    _write_axis(root, "time", (dates - dates[0]).astype("i8"), None, time_attributes)
    lats = -90 + dlat * np.arange(N_LAT)
    _write_axis(root, "lat", lats, np.nan, {"units": "degrees_north"})
    lons = -180 + 0.625 * np.arange(N_LON)
    _write_axis(root, "lon", lons, np.nan, {"units": "degrees_east"})
    t2m = root.create_array(
        "T2M",
        shape=(dates.size, N_LAT, N_LON),
        chunks=chunks,
        dtype="f8",
        fill_value=np.nan,
        attributes={"units": "C", "_ARRAY_DIMENSIONS": ["time", "lat", "lon"]},
    )
    step, lat_i, lon_i = np.ogrid[:n_valid, LAT_BLOCK, LON_BLOCK]
    t2m[:n_valid, LAT_BLOCK, LON_BLOCK] = (1000 * lat_i + lon_i) * 100 + step
    zarr.consolidate_metadata(str(path), zarr_format=2)


def _write_axis(
    root: zarr.Group,
    name: str,
    values: npt.NDArray[np.generic],
    fill_value: float | None,
    attributes: dict[str, str],
) -> None:
    axis = root.create_array(
        name,
        shape=values.shape,
        chunks=values.shape,
        dtype=values.dtype,
        fill_value=fill_value,
        attributes={**attributes, "_ARRAY_DIMENSIONS": [name]},
    )
    axis[:] = values
