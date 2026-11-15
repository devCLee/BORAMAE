"""Batch commands, started by hand: python -m boramae.batch <command> [args].

Each command lives in boramae.batch.<module> and exposes main(argv) -> int.
"""

import argparse
import importlib
import sys

COMMANDS = {
    "build-catalog": "Build the variable catalog from the content seed and the stores.",
    "warm": "Compute and store the results of the demo and catalog cases.",
    "grid": "Compute the trend grid over East Asia.",
    "export-demo": "Export the demo bundle for the frontend.",
    "lint-content": "Check the content files against their models.",
    "simulate": "Run the false-alarm simulation of the trend engine.",
}
NOT_BUILT_EXIT_CODE = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m boramae.batch")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, about in COMMANDS.items():
        commands.add_parser(name, help=about, add_help=False)
    known, rest = parser.parse_known_args(argv)
    module_name = f"boramae.batch.{known.command.replace('-', '_')}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        sys.stderr.write(f"{known.command}: not built yet\n")
        return NOT_BUILT_EXIT_CODE
    return module.main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
