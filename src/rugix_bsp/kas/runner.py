"""Kas-container build execution."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from rugix_bsp.kas.project import generate_kas_config, write_kas_config
from rugix_bsp.layer import assemble_layer
from rugix_bsp.models import Board, FamilyRelease, ResolvedConfig

_BITBAKE_VAR_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)="(.*)"$')


def parse_bitbake_env(output: str) -> dict[str, str]:
    """Parse `bitbake -e` output into a variable dict."""
    variables: dict[str, str] = {}
    for line in output.splitlines():
        if line.startswith("#"):
            continue
        match = _BITBAKE_VAR_RE.match(line)
        if match:
            variables[match.group(1)] = match.group(2)
    return variables


class KasRunner:
    """Drives a Kas-based Yocto build to produce BSP artifacts.

    Directory layout:
        <work_dir>/
          kas-<board>.yaml
          meta-rugix-bsp/         # Assembled layer (next to kas config)
          build/
            tmp/deploy/images/<machine>
    """

    def __init__(self, board: Board, release: FamilyRelease, work_dir: Path) -> None:
        self.board = board
        self.release = release
        self.work_dir = work_dir.resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._yocto_vars: dict[str, str] | None = None

    @property
    def kas_config_path(self) -> Path:
        return self.work_dir / f"kas-{self.board.name}.yaml"

    @property
    def kas_lock_path(self) -> Path:
        return self.kas_config_path.with_suffix(".lock.yaml")

    @property
    def build_dir(self) -> Path:
        return self.work_dir / "build"

    @property
    def deploy_dir(self) -> Path:
        return self.build_dir / "tmp" / "deploy" / "images" / self.board.machine

    @property
    def layer_dir(self) -> Path:
        return self.work_dir / "meta-rugix-bsp"

    def generate_config(self) -> Path:
        """Assemble the layer and generate the Kas YAML configuration."""
        assemble_layer(self.board, self.release, self.work_dir)
        config = generate_kas_config(
            self.board,
            self.release,
            meta_rugix_bsp_rel="meta-rugix-bsp",
        )
        return write_kas_config(config, self.kas_config_path)

    def _env(self) -> dict[str, str]:
        env = {**os.environ}
        env["KAS_WORK_DIR"] = str(self.work_dir)
        env["KAS_BUILD_DIR"] = str(self.build_dir)
        distro = (
            self.board.kas_container_distro or self.board.family.kas_container_distro
        )
        env["KAS_CONTAINER_IMAGE_DISTRO"] = distro
        return env

    def dump_yocto_vars(self) -> dict[str, str]:
        """Dump all Yocto variables via `bitbake -e` (cached)."""
        if self._yocto_vars is not None:
            return self._yocto_vars

        config_path = self.generate_config()
        print(f"Dumping Yocto variables for {self.board.name}...")
        result = subprocess.run(
            [
                "kas-container",
                "shell",
                str(config_path),
                "-c",
                "bitbake -e virtual/kernel",
            ],
            capture_output=True,
            text=True,
            check=True,
            env=self._env(),
        )
        self._yocto_vars = parse_bitbake_env(result.stdout)
        return self._yocto_vars

    def resolve(self) -> ResolvedConfig:
        """Resolve build-output-dependent config from Yocto variables."""
        return self.board.family.resolve(self.dump_yocto_vars())

    def lock(self) -> Path:
        """Generate the Kas lockfile with exact commit hashes."""
        config_path = self.generate_config()
        subprocess.run(
            ["kas-container", "lock", str(config_path)],
            check=True,
            env=self._env(),
        )
        return self.kas_lock_path

    def build(self) -> Path:
        """Run the full Yocto build and return the deploy directory."""
        config_path = self.generate_config()
        print(f"Generating Kas lockfile for {self.board.name}...")
        subprocess.run(
            ["kas-container", "lock", str(config_path)],
            check=True,
            env=self._env(),
        )
        print(f"Building {self.board.name}...")
        subprocess.run(
            ["kas-container", "build", str(config_path)],
            check=True,
            env=self._env(),
        )
        return self.deploy_dir
