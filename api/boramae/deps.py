"""The one dependency seam: routers get every collaborator through FastAPI Depends.

Each factory imports its class inside the function, so this module loads before the
reader, the stores and the services exist. Tests replace a factory through
app.dependency_overrides (tests/fakes.py make_client).
"""

import threading
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request

from boramae.config import Settings, load_settings
from boramae.ports import ObjectStore, SeriesReader

if TYPE_CHECKING:
    from boramae.services.parser_llm import ModelParser
    from boramae.store.pool import WorkerPool
    from boramae.store.results import ResultService

FILE_SCHEME = "file:"
S3_SCHEME = "s3"
_RESULTS_LOCK = threading.Lock()


def get_settings() -> Settings:
    return load_settings()


# ponytail: functools.cache can build twice when the first two requests race; the
# spare object serves one request. Build at startup if that ever matters.
@cache
def get_reader() -> SeriesReader:
    from boramae.power.reader import PowerReader

    return PowerReader(get_settings())


@cache
def get_store() -> ObjectStore:
    """file:<folder> gives the local store, s3://<bucket> the S3 store."""
    settings = get_settings()
    url = settings.store_url
    if url.startswith(FILE_SCHEME):
        from boramae.store.local import LocalStore

        return LocalStore(Path(url.removeprefix(FILE_SCHEME)))
    parts = urlsplit(url)
    if parts.scheme == S3_SCHEME and parts.netloc and parts.path in ("", "/"):
        import boto3

        from boramae.store.s3 import S3Store

        client = boto3.client("s3", region_name=settings.aws_region)
        return S3Store(parts.netloc, client)
    raise ValueError(
        f"BORAMAE_STORE_URL: expected file:<folder> or s3://<bucket>, got {url!r}"
    )


@cache
def get_pool() -> "WorkerPool":
    from boramae.store.pool import WorkerPool

    settings = get_settings()
    return WorkerPool(settings.pool_size, settings.pool_wait_s)


def get_results(
    request: Request,
    store: Annotated[ObjectStore, Depends(get_store)],
    pool: Annotated["WorkerPool", Depends(get_pool)],
) -> "ResultService":
    """One ResultService per app, built on first use from the (overridable) store."""
    state = request.app.state
    with _RESULTS_LOCK:
        if getattr(state, "results", None) is None:
            from boramae.store.results import ResultService

            state.results = ResultService(store, pool)
        return state.results


def get_catalog(store: Annotated[ObjectStore, Depends(get_store)]) -> object:
    from boramae.services.catalog import load_catalog

    return load_catalog(store)


@cache
def get_model_parser() -> "ModelParser | None":
    from boramae.services.parser_llm import make_model_parser

    return make_model_parser(get_settings())
