"""The variable catalog: load meta/catalog.json once per store and look entries up."""

from boramae.contracts.results_catalog import Catalog, CatalogMetric, CatalogVariable
from boramae.errors import ProblemError
from boramae.ports import ObjectStore
from boramae.store.results import HEADER_RETRY_AFTER, RETRY_AFTER_S

CATALOG_PATH = "meta/catalog.json"
UNAVAILABLE_STATUS = 503
CATALOG_MISSING_CODE = "catalog_unavailable"  # the code of routers/meta.py

# ponytail: the copy lives as long as the process, so a catalog that build-catalog
# publishes later takes effect at the next restart (DEC-006 pins one version). The
# entry keeps its store, so no new store can reuse the id. Re-read on a timer if a
# running service must switch versions.
_LOADED: dict[int, tuple[ObjectStore, Catalog]] = {}


def load_catalog(store: ObjectStore) -> Catalog:
    """The stored catalog, read and validated on the first call for a store.

    Raises ProblemError 503 while the store holds no catalog; a later call reads again.
    """
    loaded = _LOADED.get(id(store))
    if loaded is None:
        body = store.get(CATALOG_PATH)
        if body is None:
            raise ProblemError(
                UNAVAILABLE_STATUS,
                CATALOG_MISSING_CODE,
                f"{CATALOG_PATH} is not built; run build-catalog",
                headers={HEADER_RETRY_AFTER: str(RETRY_AFTER_S)},
            )
        loaded = _LOADED[id(store)] = (store, Catalog.model_validate_json(body))
    return loaded[1]


def find_variable(catalog: Catalog, var_id: str) -> CatalogVariable | None:
    return next((item for item in catalog.variables if item.id == var_id), None)


def find_metric(catalog: Catalog, metric_id: str) -> CatalogMetric | None:
    return next((item for item in catalog.metrics if item.id == metric_id), None)


def list_scan_set(catalog: Catalog) -> list[CatalogVariable]:
    """The variables that the no-trend scan tests, in catalog order (Q-18)."""
    return [item for item in catalog.variables if item.scan_set]
