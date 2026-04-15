"""OCI distribution of BSP archives via oras."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rugix_bsp.models import Board

DEFAULT_REGISTRY = "ghcr.io/rugix/rugix-bsps"
MEDIA_TYPE = "application/vnd.rugix.bsp.v1.tar+gzip"


def push_bsp(
    archive: Path,
    board: Board,
    release: str,
    version: str,
    registry: str = DEFAULT_REGISTRY,
    build_hash: str = "",
) -> str:
    """Push a BSP archive to an OCI registry via oras."""
    ref = f"{registry}/{board.name}:{release}-{version}"
    cmd = [
        "oras",
        "push",
        ref,
        f"{archive}:{MEDIA_TYPE}",
        "--annotation",
        f"org.rugix.bsp.name={board.name}",
        "--annotation",
        f"org.rugix.bsp.architecture={board.family.architecture}",
        "--annotation",
        f"org.rugix.bsp.release={release}",
        "--annotation",
        f"org.rugix.bsp.support={board.support}",
    ]
    if build_hash:
        cmd.extend(["--annotation", f"org.rugix.bsp.build-hash={build_hash}"])
    subprocess.run(cmd, check=True)

    # Also tag as latest for this release.
    subprocess.run(["oras", "tag", ref, f"{release}-latest"], check=True)

    return ref


def check_exists(
    board_name: str,
    build_hash: str,
    registry: str = DEFAULT_REGISTRY,
) -> bool:
    """Check if a BSP with this build hash already exists in the registry."""
    result = subprocess.run(
        ["oras", "discover", f"{registry}/{board_name}", "--artifact-type", MEDIA_TYPE],
        capture_output=True,
        text=True,
    )
    return build_hash in result.stdout
