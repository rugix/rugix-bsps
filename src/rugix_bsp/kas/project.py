"""Kas YAML configuration generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rugix_bsp.models import Board, BoardFamily, FamilyRelease


def generate_kas_config(
    board: Board,
    release: FamilyRelease,
    meta_rugix_bsp_rel: str | None = None,
) -> dict[str, Any]:
    """Generate a Kas YAML configuration dict from a board + release."""
    family = board.family
    targets = release.kas_targets or family.kas_targets

    config: dict[str, Any] = {
        "header": {"version": 14},
        "machine": board.machine,
        "distro": family.kas_distro,
        "target": list(targets),
    }

    local_conf_parts: dict[str, str] = {}
    merged_conf = _merge_local_conf(family, release, board)
    if merged_conf:
        local_conf_parts["board-conf"] = merged_conf
    config["local_conf_header"] = local_conf_parts

    repos = _merge_repos(family, release, board)
    if meta_rugix_bsp_rel is not None:
        repos["meta-rugix-bsp"] = {"path": meta_rugix_bsp_rel}
    config["repos"] = repos

    return config


def write_kas_config(config: dict[str, Any], path: Path) -> Path:
    """Write a Kas configuration dict to a YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return path


def _merge_local_conf(family: BoardFamily, release: FamilyRelease, board: Board) -> str:
    parts: list[str] = []
    if family.local_conf:
        parts.append(family.local_conf)
    if release.local_conf:
        parts.append(release.local_conf)
    if board.extra_local_conf:
        parts.append(board.extra_local_conf)
    return "\n".join(parts)


def _merge_repos(
    family: BoardFamily, release: FamilyRelease, board: Board
) -> dict[str, Any]:
    repos: dict[str, Any] = {}
    repos.update(release.resolve_repos())
    repos.update(board.repos_for_release(release.name))
    return repos
