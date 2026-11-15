import json

import pytest

from boramae.batch.lint_content import main

MECHANISM = {
    "en": "Warmer air holds more water vapour.",
    "ko": "따뜻한 공기는 수증기를 더 품어요.",
}
CAPTION = {"en": "Choose a language", "ko": "언어를 골라요"}
QUESTION = {
    "ko": "서울 첫눈이 늦어지고 있나요?",
    "en": "Is Seoul's first snow coming later?",
}
AREA = {"lat": 37.5665, "lon": 126.978, "radius_km": 25}
WINDOW = {"start": 1981, "end": "latest"}
NO_METRIC_DEFAULTS = {"months": None, "threshold": None, "op": None}


def _request_spec(kind):
    return {
        "v": 1,
        "kind": kind,
        "var": "PRECSNO",
        "metric": {
            "id": "first_date",
            "threshold": "0.1",
            "op": ">=",
            "months": None,
            "season_start": "08-01",
        },
        "area": AREA,
        "window": WINDOW,
    }


def _link(link_id):
    return {
        "id": link_id,
        "driver": {
            "var": "T2M",
            "metric": {"id": "seasonal_mean"} | NO_METRIC_DEFAULTS,
        },
        "response": {
            "var": "PRECSNO",
            "metric": {"id": "first_date"} | NO_METRIC_DEFAULTS,
        },
        "expected_sign": "+",
        "mechanism": MECHANISM,
        "scale": "regional",
        "area": "user",
        "lag_years": 0,
        "status": "robust",
        "doi": "10.1175/JCLI3850.1",
        "url": None,
        "citation": "Knowles et al. 2006",
    }


def _board(drivers):
    return {
        "id": "CB-01",
        "title": {"en": "Snow", "ko": "눈"},
        "focus": [{"var": "PRECSNO", "metric_id": "first_date"}],
        "drivers": drivers,
        "responses": [],
    }


def _chip(input_id):
    return {
        "input_id": input_id,
        "country": "KR",
        "seasons": ["winter"],
        "intent": "timing",
    }


def _script(case_id):
    step = {
        "id": "s1",
        "action": "choose_language",
        "args": {"lang": "ko"},
        "caption": CAPTION,
        "is_verdict_step": False,
    }
    return {"id": "first-snow-seoul", "case_id": case_id, "steps": [step]}


VALID_SET = {
    "catalog.seed.json": {
        "variables": [
            {
                "id": "PRECSNO",
                "name": {"en": "Snowfall", "ko": "강설량"},
                "definition": {
                    "en": "Precipitation that falls as snow.",
                    "ko": "눈으로 내린 강수예요.",
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
        "metrics": [
            {
                "id": "first_date",
                "name": {"en": "First date", "ko": "첫 날짜"},
                "definition": {
                    "en": "First day past the threshold.",
                    "ko": "기준을 처음 넘은 날이에요.",
                },
                "source_freq": "daily",
                "value_kind": "date",
                "default_months": None,
                "default_threshold": "0.1",
                "op": ">=",
                "unit_rule": "day_of_season",
            }
        ],
        "unavailable": [
            {
                "id": "PM25",
                "names": {"en": ["PM2.5"], "ko": ["초미세먼지"]},
                "nearest_var": None,
            }
        ],
    },
    "catalog-inputs.json": {
        "inputs": [
            {
                "id": 1,
                "theme": "Winter",
                "text": QUESTION,
                "intent": "timing",
                "place": {"name": {"ko": "서울", "en": "Seoul"}, "country": "KR"},
                "months": None,
                "threshold_text": "≥ 0.1 mm",
                "metric_text": "First-snow date",
                "data_text": "POWER daily",
                "board": "CB-01",
                "power_only": True,
                "expected": {
                    "var": "PRECSNO",
                    "metric_id": "first_date",
                    "months": None,
                    "threshold": "0.1",
                    "op": ">=",
                    "window_start": 1981,
                    "supported": True,
                },
            }
        ],
        "edge_cases": [
            {
                "id": "E1",
                "text": {"ko": "내일 비 와요?", "en": "Will it rain tomorrow?"},
                "reply_class": "forecast",
                "reply_text": None,
            }
        ],
    },
    "registry.json": [_link("t2m-first-snow")],
    "boards.json": [_board(["t2m-first-snow"])],
    "keywords.json": [
        {
            "keywords": {"ko": ["첫눈"], "en": ["first snow"]},
            "var": "PRECSNO",
            "metric_id": "first_date",
            "intent": "timing",
            "default_months": None,
            "default_threshold": "0.1",
            "op": ">=",
        }
    ],
    "gazetteer.json": [
        {
            "id": "seoul",
            "name": {"en": "Seoul", "ko": "서울"},
            "alt": ["서울시"],
            "lat": 37.5665,
            "lon": 126.978,
            "country": "KR",
            "kind": "city",
        }
    ],
    "chips.json": [_chip(1)],
    "licenses.json": [
        {
            "name": "NASA POWER",
            "kind": "data",
            "license": "public domain",
            "url": "https://power.larc.nasa.gov/",
            "citation": "NASA POWER Project",
            "is_verified": False,
        }
    ],
    "demo/cases.json": [
        {
            "id": "first-snow-seoul",
            "input_id": 1,
            "lang": "ko",
            "question": QUESTION,
            "area": AREA,
            "window": WINDOW,
            "specs": {
                "trend": _request_spec("trend"),
                "caseboard": _request_spec("caseboard"),
                "scan": None,
            },
            "prompts": [{"id": "p1", "text": {"ko": "왜요?", "en": "Why?"}}],
        }
    ],
    "demo/scripts/first-snow-seoul.json": _script("first-snow-seoul"),
    "demo/answers/first-snow-seoul.ko.json": [
        {
            "prompt_id": "p1",
            "lang": "ko",
            "text": "답이에요.",
            "result_keys": [],
            "citations": [],
        }
    ],
}


def _write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("BORAMAE_CONTENT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def valid_root(root):
    for rel, data in VALID_SET.items():
        _write(root, rel, data)
    return root


def test_empty_content_folder_passes(root):
    assert main([]) == 0


def test_valid_set_passes(valid_root):
    assert main([]) == 0


def test_valid_set_reports_every_file(valid_root, capsys):
    main([])
    assert f"{len(VALID_SET)} files" in capsys.readouterr().out


def test_board_that_names_a_missing_link_fails(valid_root):
    _write(valid_root, "boards.json", [_board(["t2m-first-snow", "missing-link"])])
    assert main(["--only", "registry,boards"]) == 1


def test_board_error_names_file_and_field(valid_root, capsys):
    _write(valid_root, "boards.json", [_board(["missing-link"])])
    main(["--only", "registry,boards"])
    assert "boards.json: 0.drivers.0:" in capsys.readouterr().out


def test_unknown_field_error_names_file_and_field(valid_root, capsys):
    _write(valid_root, "registry.json", [_link("t2m-first-snow") | {"note": "x"}])
    main(["--only", "registry"])
    assert "registry.json: 0.note:" in capsys.readouterr().out


def test_only_registry_ignores_a_broken_gazetteer(valid_root):
    _write(valid_root, "gazetteer.json", "{broken")
    assert main(["--only", "registry"]) == 0


def test_broken_gazetteer_fails_the_full_run(valid_root):
    _write(valid_root, "gazetteer.json", "{broken")
    assert main([]) == 1


@pytest.mark.parametrize(
    "rel",
    [
        "probe.json",
        "evidence/false-alarm.json",
        "golden/cells.json",
        "suites/red-team.json",
    ],
)
def test_file_with_no_model_is_skipped(valid_root, rel):
    _write(valid_root, rel, "{not json")
    assert main([]) == 0


def test_chip_that_names_an_unknown_input_fails(valid_root):
    _write(valid_root, "chips.json", [_chip(99)])
    assert main(["--only", "inputs,chips"]) == 1


def test_demo_script_that_names_an_unknown_case_fails(valid_root):
    _write(valid_root, "demo/scripts/other.json", _script("no-such-case"))
    assert main(["--only", "demo"]) == 1


def test_broken_demo_answer_fails(valid_root):
    _write(valid_root, "demo/answers/first-snow-seoul.en.json", [{"prompt_id": "p1"}])
    assert main(["--only", "demo"]) == 1


def test_unknown_only_name_is_refused(root):
    with pytest.raises(SystemExit):
        main(["--only", "registry,glossary"])
