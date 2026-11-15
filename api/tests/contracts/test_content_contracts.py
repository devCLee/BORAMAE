import json

import pytest
from pydantic import ValidationError

from boramae.contracts.content import (
    Board,
    CatalogInput,
    CatalogSeed,
    DemoScript,
    RegistryLink,
)
from boramae.services.content import load_content


def _side(var, metric_id="annual_mean"):
    return {
        "var": var,
        "metric": {"id": metric_id, "months": None, "threshold": None, "op": None},
    }


def _link(**changes):
    row = {
        "id": "t2m-tqv",
        "driver": _side("T2M"),
        "response": _side("TQV"),
        "expected_sign": "+",
        "mechanism": {
            "en": "Warmer air holds more water vapour.",
            "ko": "따뜻한 공기는 수증기를 더 품어요.",
        },
        "scale": "global",
        "area": "user",
        "lag_years": 0,
        "status": "robust",
        "doi": "10.1175/JCLI3990.1",
        "url": None,
        "citation": "Held & Soden 2006",
    }
    return row | changes


def _seed(definition_ko="눈 형태로 내린 강수량이에요."):
    return {
        "variables": [
            {
                "id": "PRECSNO",
                "name": {"en": "Snowfall", "ko": "강설량"},
                "definition": {
                    "en": "Precipitation that falls as snow.",
                    "ko": definition_ko,
                },
                "dataset": "POWER MERRA-2",
                "kind": "model",
                "min_record_years": 20,
                "default_metric": "first_date",
                "scan_set": True,
                "share_scale": None,
                "nearest_available": None,
            }
        ],
        "metrics": [],
        "unavailable": [],
    }


def _board(drivers):
    return {
        "id": "CB-03",
        "title": {"en": "Heavy rain", "ko": "폭우"},
        "focus": [{"var": "PRECTOTCORR", "metric_id": "rx1day"}],
        "drivers": drivers,
        "responses": [],
    }


def _input(expected):
    return {
        "id": 10,
        "theme": "Rain",
        "text": {
            "ko": "서울 폭우가 더 세졌나요?",
            "en": "Is Seoul's heaviest rain getting heavier?",
        },
        "intent": "extremes_intensity",
        "place": {"name": {"ko": "서울", "en": "Seoul"}, "country": "KR"},
        "months": [6, 7, 8, 9],
        "threshold_text": None,
        "metric_text": "Wettest day",
        "data_text": "POWER daily",
        "board": "CB-03",
        "power_only": True,
        "expected": expected,
    }


def _script(action):
    step = {
        "id": "s1",
        "action": action,
        "args": {"lang": "ko"},
        "caption": {"en": "Choose a language", "ko": "언어를 골라요"},
        "is_verdict_step": False,
    }
    return {"id": "first-snow-seoul", "case_id": "first-snow-seoul", "steps": [step]}


def test_registry_row_with_doi_passes():
    assert RegistryLink.model_validate(_link()).doi == "10.1175/JCLI3990.1"


def test_registry_row_without_source_fails():
    with pytest.raises(ValidationError):
        RegistryLink.model_validate(_link(doi=None, url=None))


def test_not_testable_row_with_url_and_no_doi_passes():
    row = _link(status="not_testable_here", doi=None, url="https://www.kma.go.kr/")
    assert RegistryLink.model_validate(row).status == "not_testable_here"


@pytest.mark.parametrize(
    "changes",
    [
        {"driver": _side("PM25")},
        {"response": _side("TQV", "monthly_mean")},
        {"status": "probable"},
        {"expected_sign": "±"},
        {"doi": "https://doi.org/10.1175/JCLI3990.1"},
        {"scale": ""},
        {"mechanism": {"en": "Warmer air holds more water vapour.", "ko": ""}},
    ],
    ids=[
        "variable",
        "metric",
        "status",
        "sign",
        "doi-form",
        "scale",
        "korean-mechanism",
    ],
)
def test_registry_row_outside_the_contract_fails(changes):
    with pytest.raises(ValidationError):
        RegistryLink.model_validate(_link(**changes))


def test_catalog_variable_with_complete_text_passes():
    assert CatalogSeed.model_validate(_seed()).variables[0].id == "PRECSNO"


def test_catalog_variable_with_empty_korean_definition_fails():
    with pytest.raises(ValidationError):
        CatalogSeed.model_validate(_seed(definition_ko=""))


@pytest.mark.parametrize(
    "model, data",
    [
        (RegistryLink, _link(note="extra")),
        (Board, _board([]) | {"subtitle": "extra"}),
        (CatalogSeed, _seed() | {"version": 1}),
    ],
    ids=["registry", "board", "catalog-seed"],
)
def test_unknown_field_is_an_error(model, data):
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_board_with_four_drivers_fails():
    with pytest.raises(ValidationError):
        Board.model_validate(_board(["a", "b", "c", "d"]))


def test_input_with_unavailable_reply_passes():
    expected = {"reply": "not_in_this_version", "nearest_var": "T2M"}
    assert (
        CatalogInput.model_validate(_input(expected)).expected.reply
        == "not_in_this_version"
    )


def test_input_with_mixed_expected_shape_fails():
    expected = {
        "reply": "not_in_this_version",
        "nearest_var": "T2M",
        "supported": False,
    }
    with pytest.raises(ValidationError):
        CatalogInput.model_validate(_input(expected))


def test_demo_step_outside_the_action_list_fails():
    with pytest.raises(ValidationError):
        DemoScript.model_validate(_script("fly_to"))


@pytest.fixture
def content_root(tmp_path, monkeypatch):
    monkeypatch.setenv("BORAMAE_CONTENT_DIR", str(tmp_path))
    load_content.cache_clear()
    yield tmp_path
    load_content.cache_clear()


def test_load_content_returns_the_validated_model(content_root):
    (content_root / "registry.json").write_text(json.dumps([_link()]), encoding="utf-8")
    assert load_content("registry")[0].citation == "Held & Soden 2006"


def test_load_content_keeps_the_file_in_memory(content_root):
    (content_root / "registry.json").write_text(json.dumps([_link()]), encoding="utf-8")
    assert load_content("registry") is load_content("registry")
