"""Content-hash computation for BSP change detection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rugix_bsp.models import Board, FamilyRelease


def compute_build_hash(
    board: Board,
    release: FamilyRelease,
    layer_dir: Path,
    kas_lock: Path | None = None,
) -> str:
    """Compute a deterministic SHA-256 hash of all build inputs.

    Inputs: board config, release repos, assembled layer files, and the
    Kas lockfile if available (which pins exact upstream commits).
    """
    h = hashlib.sha256()

    h.update(_board_canonical(board, release).encode())

    if kas_lock is not None and kas_lock.exists():
        h.update(kas_lock.read_bytes())
    else:
        h.update(json.dumps(release.repos, sort_keys=True).encode())

    if layer_dir.is_dir():
        for path in sorted(layer_dir.rglob("*")):
            if path.is_file():
                h.update(path.relative_to(layer_dir).as_posix().encode())
                h.update(path.read_bytes())

    return h.hexdigest()


def _board_canonical(board: Board, release: FamilyRelease) -> str:
    """Serialize board + release to a canonical string for hashing."""
    data: dict[str, Any] = {
        "name": board.name,
        "machine": board.machine,
        "family": board.family.name,
        "release": release.name,
        "architecture": board.family.architecture,
        "kernel_recipe": board.family.kernel_recipe,
        "extra_repos": board.extra_repos,
        "extra_local_conf": board.extra_local_conf,
    }
    return json.dumps(data, sort_keys=True)
