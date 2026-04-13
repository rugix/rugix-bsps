"""BSP tar archive packing and unpacking."""

from __future__ import annotations

import tarfile
from pathlib import Path

from rugix_bsp.board import Board


def _generate_bsp_toml(board: Board) -> str:
    """Generate rugix-bsp.toml content from a Board definition."""
    lines = [
        "[bsp]",
        f'name = "{board.name}"',
        f'architecture = "{board.architecture}"',
        "",
        "[image.layout]",
        f'type = "{board.disk_layout.table_type}"',
    ]

    for blob in board.disk_layout.raw_blobs:
        lines.append("")
        lines.append("[[image.layout.raw-blobs]]")
        lines.append(f'file = "artifacts/firmware/{blob.yocto_deploy_file}"')
        lines.append(f'offset = "{blob.offset}"')

    for part in board.disk_layout.partitions:
        lines.append("")
        lines.append("[[image.layout.partitions]]")
        lines.append(f'name = "{part.name}"')
        if part.size is not None:
            lines.append(f'size = "{part.size}"')
        if part.type_uuid is not None:
            lines.append(f'type = "{part.type_uuid}"')
        lines.append(f'filesystem = {{ type = "{part.filesystem}" }}')
        if part.root is not None:
            lines.append(f'root = "{part.root}"')

    for payload in board.bundle_payloads:
        lines.append("")
        lines.append("[[bundle.payloads]]")
        lines.append(f'slot = "{payload.slot}"')
        if payload.partition is not None:
            lines.append(f"partition = {payload.partition}")
        if payload.file is not None:
            lines.append(f'file = "{payload.file}"')

    lines.append("")
    return "\n".join(lines)


def _generate_readme(board: Board) -> str:
    return f"""\
# Rugix BSP: {board.name}

This archive contains pre-built binary artifacts for the **{board.name}**
board. It is intended for use with [Rugix Bakery](https://rugix.dev) but
the artifacts (kernel, device trees, firmware, kernel modules) can be used
independently.

## Contents

- `roots/` — Files overlaid onto the Rugix Bakery layer roots (config and
  system partitions).
- `artifacts/firmware/` — Raw firmware blobs written at fixed disk offsets
  during image assembly.
- `bsp/rugix-bsp.toml` — Machine-readable BSP metadata (disk layout, boot
  flow, partition mapping).
- `bsp/kas.lock.yaml` — KAS lockfile pinning the exact Yocto layer commits
  used to build these artifacts. This serves as a source reference for
  license compliance and reproducibility.
- `bsp/license-manifest.csv` — License information for every recipe
  involved in the build.
- `bsp/licenses/` — Full license texts collected by the Yocto build system.

## Source Traceability

All artifacts were built from Yocto/OpenEmbedded recipes. The file
`bsp/kas.lock.yaml` records the exact Git commit of every layer used in the
build. To reproduce the build or obtain the corresponding source code,
check out the listed commits and run the build with
[KAS](https://kas.readthedocs.io/).

## License Notice

This archive contains binaries built from multiple open-source and
proprietary components. Individual license terms are listed in
`bsp/license-manifest.csv`. Some components (e.g., vendor firmware blobs)
may be subject to proprietary license agreements. **It is the user's
responsibility to review and comply with all applicable license terms
before redistribution.**
"""


def pack_bsp(board: Board, staging_dir: Path, output: Path) -> Path:
    """Pack a BSP staging directory into a tar.gz archive.

    The staging_dir mirrors the layer structure (roots/, artifacts/, bsp/).
    """
    bsp_dir = staging_dir / "bsp"
    bsp_dir.mkdir(parents=True, exist_ok=True)
    (bsp_dir / "rugix-bsp.toml").write_text(_generate_bsp_toml(board))
    (staging_dir / "README.md").write_text(_generate_readme(board))

    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Packing BSP archive {output.name}...")
    with tarfile.open(output, "w:gz", compresslevel=1) as tar:
        tar.add(str(staging_dir), arcname=".", recursive=True)

    return output
