"""Settings of the API process, read from BORAMAE_ environment variables."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace

ENV_PREFIX = "BORAMAE_"
_TRUE_WORDS = frozenset({"1", "true", "on", "yes"})
_FALSE_WORDS = frozenset({"0", "false", "off", "no", ""})


# ponytail: every timeout, limit and budget below is a placeholder (TRD Q-22, Q-23;
# TDD.md:366, DEC-009); set the measured values through the environment.
@dataclass(frozen=True)
class Settings:
    store_url: str = "file:.data"
    content_dir: str = "../content"
    llm_enabled: bool = False
    model_id: str | None = None
    aws_region: str = "us-west-2"
    compute_location: str = "local"
    dev_cors_origin: str | None = None
    parse_model_timeout_s: float = 4.0
    power_chunk_timeout_s: float = 10.0
    context_timeout_s: float = 5.0
    guide_model_timeout_s: float = 30.0
    request_timeout_s: float = 60.0
    pool_size: int = 4
    pool_wait_s: float = 15.0
    llm_session_cap: int = 20
    llm_daily_budget: int = 2000
    chunk_cache_bytes: int = 2**30


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Return the defaults, overridden by BORAMAE_<FIELD> variables that are set.

    A BORAMAE_ name that matches no field raises, so a misspelled override fails.
    """
    env = os.environ if environ is None else environ
    known = {ENV_PREFIX + field.name.upper() for field in fields(Settings)}
    unknown = sorted(n for n in env if n.startswith(ENV_PREFIX) and n not in known)
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(unknown)}")
    defaults = Settings()
    overrides = {}
    for field in fields(Settings):
        name = ENV_PREFIX + field.name.upper()
        if name in env:
            default = getattr(defaults, field.name)
            overrides[field.name] = _convert(name, env[name], default)
    return replace(defaults, **overrides)


def _convert(name: str, raw: str, default: object) -> object:
    try:
        if isinstance(default, bool):
            return _to_bool(raw)
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
        return raw
    except ValueError as exc:
        raise ValueError(f"{name}: cannot read {raw!r}") from exc


def _to_bool(raw: str) -> bool:
    word = raw.strip().lower()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    raise ValueError(f"not a switch value: {raw!r}")
