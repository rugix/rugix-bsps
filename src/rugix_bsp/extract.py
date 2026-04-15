"""Artifact extraction from Yocto deploy directory."""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from rugix_bsp.archive import pack_bsp
from rugix_bsp.layer import REPO_ROOT
from rugix_bsp.models import Board, FamilyRelease, ResolvedConfig


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
    """Extract kernel modules into usr/lib/modules/ (Debian layout)."""
    usr_lib_modules = dest / "usr" / "lib" / "modules"
    usr_lib_modules.mkdir(parents=True, exist_ok=True)
    with tarfile.open(modules_tar) as tar:
        for member in tar.getmembers():
            for prefix in ("./lib/modules/", "lib/modules/"):
                if member.name.startswith(prefix):
                    member.name = member.name[len(prefix) :]
                    tar.extract(member, usr_lib_modules, filter="data")
                    break


def _collect_license_manifest(build_dir: Path, bsp_dir: Path) -> None:
    """Build a license manifest CSV from Yocto's pkgdata."""
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


def _collect_kas_project(
    kas_config: Path | None,
    kas_lock: Path | None,
    layer_dir: Path | None,
    dest: Path,
) -> None:
    """Package the Kas source project (config + custom layer, not third-party repos)."""
    kas_project = dest / "kas-project"
    kas_project.mkdir(parents=True, exist_ok=True)
    if kas_config is not None and kas_config.exists():
        shutil.copy2(kas_config, kas_project / "kas.yaml")
    if kas_lock is not None and kas_lock.exists():
        shutil.copy2(kas_lock, kas_project / "kas.lock.yaml")
    if layer_dir is not None and layer_dir.exists():
        shutil.copytree(layer_dir, kas_project / "meta-rugix-bsp")


def extract_bsp(
    board: Board,
    release: FamilyRelease,
    resolved: ResolvedConfig,
    deploy_dir: Path,
    output: Path,
    *,
    kas_config: Path | None = None,
    kas_lock: Path | None = None,
    layer_dir: Path | None = None,
    build_dir: Path | None = None,
    build_hash: str = "",
) -> Path:
    """Extract BSP artifacts from a Yocto deploy dir and pack a BSP archive."""
    staging = output.parent / f".staging-{board.name}"
    if staging.exists():
        shutil.rmtree(staging)

    config_root = staging / "roots" / "config"
    boot_root = staging / "roots" / "boot"
    system_root = staging / "roots" / "system"
    artifacts_dir = staging / "artifacts" / "firmware"
    config_root.mkdir(parents=True)
    boot_root.mkdir(parents=True)
    system_root.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)

    # roots/config/ — boot script and bootstrap marker.
    boot_scr = _find_file(deploy_dir, "boot.scr")
    if boot_scr is not None:
        shutil.copy2(boot_scr, config_root / "boot.scr")
    (config_root / ".rugix").mkdir()
    (config_root / ".rugix" / "bootstrap").touch()

    # roots/boot/ — kernel and device trees (dedicated boot partition).
    for kernel_name in ["Image", "zImage", "bzImage"]:
        src = _find_file(deploy_dir, kernel_name)
        if src is not None:
            shutil.copy2(src, boot_root / kernel_name)
            break

    dtb_dir = boot_root / "dtbs"
    dtb_dir.mkdir()
    for dtb in deploy_dir.glob("*.dtb"):
        if not dtb.is_symlink():
            shutil.copy2(dtb, dtb_dir / dtb.name)

    # roots/system/ — kernel modules.
    modules_tar = _find_modules_tar(deploy_dir)
    if modules_tar is not None:
        _extract_modules(modules_tar, system_root)

    # rugix-ctrl configuration.
    rugix_dir = system_root / "etc" / "rugix"
    rugix_dir.mkdir(parents=True)
    system_toml = resolved.system_toml or _load_template("system.toml")
    bootstrapping_toml = resolved.bootstrapping_toml or _load_template(
        "bootstrapping.toml"
    )
    if system_toml:
        (rugix_dir / "system.toml").write_text(system_toml)
    if bootstrapping_toml:
        (rugix_dir / "bootstrapping.toml").write_text(bootstrapping_toml)

    # U-Boot environment config.
    fw_env = REPO_ROOT / "templates" / "fw_env.config"
    if fw_env.exists():
        shutil.copy2(fw_env, system_root / "etc" / "fw_env.config")

    # artifacts/firmware/
    for blob in resolved.disk_layout.raw_blobs:
        src = _find_file(deploy_dir, blob.deploy_file)
        if src is None:
            raise FileNotFoundError(
                f"blob {blob.deploy_file!r} not found in {deploy_dir}"
            )
        shutil.copy2(src, artifacts_dir / blob.deploy_file)

    # bsp/ metadata
    bsp_dir = staging / "bsp"
    bsp_dir.mkdir(parents=True, exist_ok=True)

    _collect_kas_project(kas_config, kas_lock, layer_dir, bsp_dir)

    if build_dir is not None:
        _collect_license_manifest(build_dir, bsp_dir)
        licenses_src = build_dir / "tmp" / "deploy" / "licenses"
        if licenses_src.exists():
            shutil.copytree(licenses_src, bsp_dir / "licenses")

    result = pack_bsp(board, release, resolved, staging, output, build_hash=build_hash)
    shutil.rmtree(staging)
    return result


def _load_template(name: str) -> str:
    path = REPO_ROOT / "templates" / name
    if path.exists():
        return path.read_text()
    return ""
