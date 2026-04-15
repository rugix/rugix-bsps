"""Yocto layer assembly from components."""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

from rugix_bsp.models import Board, FamilyRelease

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAYERS_COMMON = REPO_ROOT / "layers" / "common"


def _family_dir(board: Board) -> Path:
    """Resolve the family package directory on disk."""
    module_name = f"rugix_bsp.families.{board.family.name.replace('-', '_')}"
    module = importlib.import_module(module_name)
    assert module.__file__ is not None
    return Path(module.__file__).resolve().parent


def assemble_layer(
    board: Board,
    release: FamilyRelease,
    dest: Path,
) -> Path:
    """Assemble meta-rugix-bsp in *dest* from components and generated files.

    Returns the path to the assembled layer directory.
    """
    layer_dir = dest / "meta-rugix-bsp"
    if layer_dir.exists():
        shutil.rmtree(layer_dir)

    # 1. Copy common layer components.
    shutil.copytree(LAYERS_COMMON, layer_dir)

    # 2. Copy family-specific boot.cmd into the boot-script recipe.
    family_dir = _family_dir(board)
    boot_cmd = family_dir / "boot.cmd"
    if boot_cmd.exists():
        files_dir = layer_dir / "recipes-bsp" / "rugix-boot-script" / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(boot_cmd, files_dir / "boot.cmd")

    # 3. Generate kernel bbappend for the board's kernel recipe.
    kernel_dir = layer_dir / "recipes-kernel" / "linux"
    kernel_dir.mkdir(parents=True, exist_ok=True)
    kernel_recipe = board.family.kernel_recipe
    bbappend = kernel_dir / f"{kernel_recipe}_%.bbappend"
    bbappend.write_text(
        'FILESEXTRAPATHS:prepend := "${THISDIR}/files:"\n'
        'SRC_URI:append = " file://rugix.cfg"\n'
    )

    return layer_dir
