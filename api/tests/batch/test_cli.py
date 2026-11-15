import sys
from types import SimpleNamespace

import pytest

from boramae.batch.__main__ import main

SUBCOMMANDS = [
    "build-catalog",
    "warm",
    "grid",
    "export-demo",
    "lint-content",
    "simulate",
]


class FakeCommand:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code
        self.argv: list[str] | None = None

    def main(self, argv: list[str]) -> int:
        self.argv = argv
        return self.exit_code


@pytest.mark.parametrize("name", SUBCOMMANDS)
def test_help_lists_the_subcommand(capsys, name):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert name in capsys.readouterr().out


def test_help_exits_with_code_0():
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0


def test_unknown_subcommand_is_a_usage_error():
    with pytest.raises(SystemExit) as exit_info:
        main(["deploy"])
    assert exit_info.value.code == 2


def test_module_not_built_yet_exits_with_code_2(monkeypatch):
    monkeypatch.setitem(sys.modules, "boramae.batch.warm", None)
    assert main(["warm"]) == 2


def test_module_not_built_yet_says_so(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "boramae.batch.warm", None)
    main(["warm"])
    assert "not built yet" in capsys.readouterr().err


def test_subcommand_returns_the_exit_code_of_its_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "boramae.batch.grid", FakeCommand(exit_code=7))
    assert main(["grid"]) == 7


def test_subcommand_passes_its_arguments_to_its_module(monkeypatch):
    command = FakeCommand(exit_code=0)
    monkeypatch.setitem(sys.modules, "boramae.batch.lint_content", command)
    main(["lint-content", "--only", "registry,boards"])
    assert command.argv == ["--only", "registry,boards"]


def test_dashed_subcommand_imports_the_underscored_module(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "boramae.batch.export_demo", SimpleNamespace(main=lambda argv: 5)
    )
    assert main(["export-demo"]) == 5
