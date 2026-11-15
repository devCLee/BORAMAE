"""TR-D-001 acceptance 1: code and content hold no POWER API address."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
POWER_API_ADDRESS = b"power.larc.nasa.gov/api"


def find_files_holding(root: Path, needle: bytes) -> list[str]:
    files = (path for path in root.rglob("*") if path.is_file())
    return sorted(str(path) for path in files if needle in path.read_bytes())


@pytest.mark.parametrize("folder", ["api/boramae", "web/src", "content"])
def test_should_hold_no_power_api_address(folder):
    assert find_files_holding(REPO_ROOT / folder, POWER_API_ADDRESS) == []


def test_should_find_a_file_that_holds_the_address(tmp_path):
    planted = tmp_path / "client.py"
    planted.write_bytes(b"URL = 'https://" + POWER_API_ADDRESS + b"/temporal'")
    assert find_files_holding(tmp_path, POWER_API_ADDRESS) == [str(planted)]
