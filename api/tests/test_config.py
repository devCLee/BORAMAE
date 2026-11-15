import pytest

from boramae.config import load_settings


def test_store_defaults_to_the_local_folder():
    assert load_settings({}).store_url == "file:.data"


def test_llm_is_off_by_default():
    assert load_settings({}).llm_enabled is False


@pytest.mark.parametrize(
    ("name", "raw", "field", "expected"),
    [
        ("BORAMAE_AWS_REGION", "ap-northeast-2", "aws_region", "ap-northeast-2"),
        ("BORAMAE_LLM_ENABLED", "on", "llm_enabled", True),
        ("BORAMAE_POOL_SIZE", "8", "pool_size", 8),
        ("BORAMAE_PARSE_MODEL_TIMEOUT_S", "2.5", "parse_model_timeout_s", 2.5),
        ("BORAMAE_POWER_CHUNK_TIMEOUT_S", "60", "power_chunk_timeout_s", 60.0),
        (
            "BORAMAE_DEV_CORS_ORIGIN",
            "http://localhost:3000",
            "dev_cors_origin",
            "http://localhost:3000",
        ),
    ],
)
def test_environment_variable_overrides_its_setting(name, raw, field, expected):
    assert getattr(load_settings({name: raw}), field) == expected


def test_process_environment_is_read_by_default(monkeypatch):
    monkeypatch.setenv("BORAMAE_AWS_REGION", "ap-northeast-2")
    assert load_settings().aws_region == "ap-northeast-2"


def test_unreadable_value_names_its_variable():
    with pytest.raises(ValueError, match="BORAMAE_POOL_SIZE"):
        load_settings({"BORAMAE_POOL_SIZE": "many"})


def test_unknown_variable_is_rejected_by_name():
    with pytest.raises(ValueError, match="BORAMAE_TIMEOUT_POWER_CHUNK_S"):
        load_settings({"BORAMAE_TIMEOUT_POWER_CHUNK_S": "60"})
