"""Artifact extraction from Yocto deploy directory."""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from rugix_bsp.archive import pack_bsp
from rugix_bsp.board import Board


def _collect_license_manifest(build_dir: Path, bsp_dir: Path) -> None:
    """Build a license manifest from Yocto's pkgdata.

    Scans pkgdata/*/runtime/* for LICENSE and PV fields to produce a CSV
    manifest covering all recipes (including transitive build deps like
    firmware-imx).
    """
    pkgdata_root = build_dir / "tmp" / "pkgdata"
    if not pkgdata_root.exists():
        return

    seen: dict[str, tuple[str, str]] = {}
    for runtime_dir in pkgdata_root.glob("*/runtime"):
        for pkg_file in runtime_dir.iterdir():
            if not pkg_file.is_file():
                continue
            license_val = ""
            pv_val = ""
            recipe_val = ""
            for line in pkg_file.read_text(errors="replace").splitlines():
                if line.startswith("LICENSE:"):
                    license_val = line.split(": ", 1)[1].strip()
                elif line.startswith("PV:"):
                    pv_val = line.split(": ", 1)[1].strip()
                elif line.startswith("PN:"):
                    recipe_val = line.split(": ", 1)[1].strip()
            if recipe_val and license_val and recipe_val not in seen:
                seen[recipe_val] = (license_val, pv_val)

    if not seen:
        return

    manifest = bsp_dir / "license-manifest.csv"
    with open(manifest, "w") as f:
        f.write("recipe,license,version\n")
        for recipe in sorted(seen):
            license_val, pv_val = seen[recipe]
            f.write(f"{recipe},{license_val},{pv_val}\n")


def _find_file(deploy_dir: Path, name: str) -> Path | None:
    """Find a file in deploy_dir, following symlinks."""
    candidate = deploy_dir / name
    if candidate.exists():
        return candidate
    matches = list(deploy_dir.glob(f"{name}*"))
    return matches[0] if matches else None


def _find_modules_tar(deploy_dir: Path) -> Path | None:
    """Find the kernel modules tarball deployed by the kernel recipe."""
    for pattern in ["modules-*.tgz", "modules-*.tar.gz"]:
        matches = list(deploy_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _extract_modules(modules_tar: Path, dest: Path) -> None:
    """Extract kernel modules into usr/lib/modules/ (Debian uses /lib -> /usr/lib)."""
    usr_lib_modules = dest / "usr" / "lib" / "modules"
    usr_lib_modules.mkdir(parents=True, exist_ok=True)
    with tarfile.open(modules_tar) as tar:
        for member in tar.getmembers():
            for prefix in ("./lib/modules/", "lib/modules/"):
                if member.name.startswith(prefix):
                    member.name = member.name[len(prefix):]
                    tar.extract(member, usr_lib_modules, filter="data")
                    break


def extract_bsp(
    board: Board,
    deploy_dir: Path,
    output: Path,
    kas_config: Path | None = None,
    kas_lock: Path | None = None,
    build_dir: Path | None = None,
) -> Path:
    """Extract BSP artifacts from a Yocto deploy dir and pack a BSP archive.

    The staging directory mirrors the Rugix Bakery layer structure:
      roots/config/   — config partition contents
      roots/system/   — system root overlay
      artifacts/      — firmware blobs for image assembly
      bsp/            — rugix-bsp.toml
    """
    staging = output.parent / f".staging-{board.name}"
    if staging.exists():
        shutil.rmtree(staging)

    config_root = staging / "roots" / "config"
    system_root = staging / "roots" / "system"
    artifacts_dir = staging / "artifacts" / "firmware"
    config_root.mkdir(parents=True)
    system_root.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)

    # --- roots/config/ ---

    # Boot script.
    boot_scr = _find_file(deploy_dir, "boot.scr")
    if boot_scr is not None:
        shutil.copy2(boot_scr, config_root / "boot.scr")

    # Bootstrap marker.
    (config_root / ".rugix").mkdir()
    (config_root / ".rugix" / "bootstrap").touch()

    # --- roots/system/ ---

    # Kernel image.
    boot_dir = system_root / "boot"
    boot_dir.mkdir()
    for kernel_name in ["Image", "zImage", "bzImage"]:
        src = _find_file(deploy_dir, kernel_name)
        if src is not None:
            shutil.copy2(src, boot_dir / kernel_name)
            break

    # Device trees.
    dtb_dir = boot_dir / "dtbs"
    dtb_dir.mkdir()
    for dtb in deploy_dir.glob("*.dtb"):
        if not dtb.is_symlink():
            shutil.copy2(dtb, dtb_dir / dtb.name)

    # Kernel modules.
    modules_tar = _find_modules_tar(deploy_dir)
    if modules_tar is not None:
        _extract_modules(modules_tar, system_root)

    # rugix-ctrl configuration.
    rugix_dir = system_root / "etc" / "rugix"
    rugix_dir.mkdir(parents=True)
    if board.system_toml:
        (rugix_dir / "system.toml").write_text(board.system_toml)
    if board.bootstrapping_toml:
        (rugix_dir / "bootstrapping.toml").write_text(board.bootstrapping_toml)

    # U-Boot environment config.
    etc_dir = system_root / "etc"
    fw_env = Path(__file__).resolve().parent / "templates" / "fw_env.config"
    if fw_env.exists():
        shutil.copy2(fw_env, etc_dir / "fw_env.config")

    # Extra deploy files.
    for extra in board.extra_deploy_files:
        src = _find_file(deploy_dir, extra)
        if src is not None:
            shutil.copy2(src, boot_dir / extra)

    # --- artifacts/firmware/ ---

    for blob in board.disk_layout.raw_blobs:
        src = _find_file(deploy_dir, blob.yocto_deploy_file)
        if src is None:
            raise FileNotFoundError(
                f"blob {blob.yocto_deploy_file!r} not found in {deploy_dir}"
            )
        shutil.copy2(src, artifacts_dir / blob.yocto_deploy_file)

    # --- bsp/ metadata ---

    bsp_dir = staging / "bsp"
    bsp_dir.mkdir(parents=True, exist_ok=True)

    # KAS config and lockfile for reproducibility and source compliance.
    if kas_config is not None and kas_config.exists():
        shutil.copy2(kas_config, bsp_dir / "kas.yaml")
    if kas_lock is not None and kas_lock.exists():
        shutil.copy2(kas_lock, bsp_dir / "kas.lock.yaml")

    # License manifest extracted from Yocto's pkgdata (covers all recipes
    # including transitive build dependencies like firmware-imx).
    if build_dir is not None:
        _collect_license_manifest(build_dir, bsp_dir)
        # Also copy the full license files from deploy/licenses if available.
        licenses_src = build_dir / "tmp" / "deploy" / "licenses"
        if licenses_src.exists():
            shutil.copytree(licenses_src, bsp_dir / "licenses")

    # rugix-bsp.toml is written by pack_bsp.

    result = pack_bsp(board, staging, output)
    shutil.rmtree(staging)
    return result
