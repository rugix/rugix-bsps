"""BSP tar archive packing."""

from __future__ import annotations

import tarfile
from pathlib import Path

from rugix_bsp.models import Board, FamilyRelease, ResolvedConfig


def _generate_bsp_toml(
    board: Board,
    release: FamilyRelease,
    resolved: ResolvedConfig,
    build_hash: str = "",
) -> str:
    """Generate rugix-bsp.toml content."""
    layout = resolved.disk_layout

    lines = [
        "[bsp]",
        f'name = "{board.name}"',
        f'architecture = "{board.family.architecture}"',
        f'release = "{release.name}"',
        f'support = "{board.support}"',
    ]
    if build_hash:
        lines.append(f'build-hash = "{build_hash}"')

    lines.extend(["", "[image.layout]", f'type = "{layout.table_type}"'])

    for blob in layout.raw_blobs:
        lines.append("")
        lines.append("[[image.layout.raw-blobs]]")
        lines.append(f'file = "artifacts/firmware/{blob.deploy_file}"')
        lines.append(f'offset = "{blob.offset}"')

    for part in layout.partitions:
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

    for payload in resolved.bundle_payloads:
        lines.append("")
        lines.append("[[bundle.payloads]]")
        lines.append(f'slot = "{payload.slot}"')
        if payload.partition is not None:
            lines.append(f"partition = {payload.partition}")
        if payload.file is not None:
            lines.append(f'file = "{payload.file}"')

    lines.append("")
    return "\n".join(lines)


def _generate_readme(board: Board, release: FamilyRelease) -> str:
    return f"""\
# Rugix BSP: {board.name}

This archive contains pre-built binary artifacts for the **{board.name}**
board (release: {release.name}). It is intended for use with
[Rugix Bakery](https://rugix.dev) but the artifacts (kernel, device trees,
firmware, kernel modules) can be used independently.

## Contents

- `roots/` — Files overlaid onto the Rugix Bakery layer roots (config and
  system partitions).
- `artifacts/firmware/` — Raw firmware blobs written at fixed disk offsets
  during image assembly.
- `bsp/rugix-bsp.toml` — Machine-readable BSP metadata (disk layout, boot
  flow, partition mapping).
- `bsp/kas-project/` — Kas configuration and custom Yocto layers used to
  build these artifacts. This serves as a source reference for license
  compliance and reproducibility.
- `bsp/license-manifest.csv` — License information for every recipe
  involved in the build.
- `bsp/licenses/` — Full license texts collected by the Yocto build system.

## Source Traceability

All artifacts were built from Yocto/OpenEmbedded recipes. The file
`bsp/kas-project/kas.lock.yaml` records the exact Git commit of every layer
used in the build. To reproduce the build or obtain the corresponding source
code, check out the listed commits and run the build with
[Kas](https://kas.readthedocs.io/).

## License Notice

This archive contains binaries built from multiple open-source and
proprietary components. Individual license terms are listed in
`bsp/license-manifest.csv`. Some components (e.g., vendor firmware blobs)
may be subject to proprietary license agreements. **It is the user's
responsibility to review and comply with all applicable license terms
before redistribution.**
"""


def pack_bsp(
    board: Board,
    release: FamilyRelease,
    resolved: ResolvedConfig,
    staging_dir: Path,
    output: Path,
    build_hash: str = "",
) -> Path:
    """Pack a BSP staging directory into a tar.gz archive."""
    bsp_dir = staging_dir / "bsp"
    bsp_dir.mkdir(parents=True, exist_ok=True)
    (bsp_dir / "rugix-bsp.toml").write_text(
        _generate_bsp_toml(board, release, resolved, build_hash)
    )
    (staging_dir / "README.md").write_text(_generate_readme(board, release))

    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Packing BSP archive {output.name}...")
    with tarfile.open(output, "w:gz", compresslevel=1) as tar:
        tar.add(str(staging_dir), arcname=".", recursive=True)

    return output
