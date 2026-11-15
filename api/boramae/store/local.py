"""Result store in a local folder, for development, tests and the demo bundle."""

import os
import time
import uuid
from pathlib import Path

DRAFT_SUFFIX = ".part"
REPLACE_RETRIES = 5
REPLACE_WAIT_S = 0.05


class LocalStore:
    """ports.ObjectStore over a folder. A store path is relative to root.

    A body is written to a draft file first, so a reader never sees a partial file.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, path: str) -> bytes | None:
        try:
            return (self.root / path).read_bytes()
        except FileNotFoundError:
            return None

    def create_once(self, path: str, body: bytes) -> bool:
        target = self.root / path
        draft = _write_draft(target, body)
        try:
            # A hard link fails when the target exists, on POSIX and on NTFS alike.
            os.link(draft, target)
        except FileExistsError:
            return False
        finally:
            draft.unlink()
        return True

    def put(self, path: str, body: bytes) -> None:
        target = self.root / path
        draft = _write_draft(target, body)
        # Windows refuses a replace while another process still holds a target
        # that was written a moment ago, so a refused replace is tried again.
        for _ in range(REPLACE_RETRIES):
            try:
                os.replace(draft, target)
            except PermissionError:
                time.sleep(REPLACE_WAIT_S)
            else:
                return
        os.replace(draft, target)


def _write_draft(target: Path, body: bytes) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    draft = target.with_name(f".{target.name}.{uuid.uuid4().hex}{DRAFT_SUFFIX}")
    draft.write_bytes(body)
    return draft
