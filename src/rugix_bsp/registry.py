"""Discovery of board families and boards."""

from __future__ import annotations

import importlib
import pkgutil
import tomllib
from pathlib import Path
from typing import Any

import rugix_bsp.families
from rugix_bsp.models import Board, BoardFamily, FamilyRelease


def _parse_board_toml(path: Path, family: BoardFamily) -> Board:
    """Parse a board TOML file and construct a Board instance."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    board_data = data.get("board", {})
    name = path.stem
    machine: str = board_data["machine"]
    description = board_data.get("description", "")
    vendor = board_data.get("vendor", "")
    support = board_data.get("support", "community")
    releases = board_data.get("releases")
    extra_local_conf = board_data.get("extra-local-conf", "")
    kas_container_distro = board_data.get("kas-container-distro")

    repo_groups: list[str] = board_data.get("repo-groups", [])
    extra_repos = _parse_repos_section(data.get("repos", {}))

    # Per-release extra repos: [release-repos."6.6.52-2.2.0".meta-arduino]
    release_repos: dict[str, dict[str, Any]] = {}
    for release_name, repos_section in data.get("release-repos", {}).items():
        release_repos[release_name] = _parse_repos_section(repos_section)

    return Board(
        name=name,
        machine=machine,
        family=family,
        description=description,
        vendor=vendor,
        support=support,
        releases=releases,
        repo_groups=repo_groups,
        extra_repos=extra_repos,
        release_repos=release_repos,
        extra_local_conf=extra_local_conf,
        kas_container_distro=kas_container_distro,
    )


def _parse_repos_section(repos_data: dict[str, Any]) -> dict[str, Any]:
    """Convert a TOML repos section into Kas repo entries."""
    result: dict[str, Any] = {}
    for repo_name, repo_def in repos_data.items():
        kas_repo: dict[str, Any] = {"url": repo_def["url"]}
        if "commit" in repo_def:
            kas_repo["commit"] = repo_def["commit"]
        if "branch" in repo_def:
            kas_repo["branch"] = repo_def["branch"]
        if "tag" in repo_def:
            kas_repo["tag"] = repo_def["tag"]
        if "layers" in repo_def:
            kas_repo["layers"] = {layer: None for layer in repo_def["layers"]}
        result[repo_name] = kas_repo
    return result


def discover_families() -> dict[str, BoardFamily]:
    """Import all family sub-packages and collect BoardFamily instances."""
    families: dict[str, BoardFamily] = {}
    for importer, modname, ispkg in pkgutil.iter_modules(
        rugix_bsp.families.__path__, rugix_bsp.families.__name__ + "."
    ):
        if not ispkg:
            continue
        module = importlib.import_module(modname)
        family = getattr(module, "FAMILY", None)
        if isinstance(family, BoardFamily):
            families[family.name] = family
    return families


def discover_boards(family: BoardFamily) -> list[Board]:
    """Scan the boards/ directory of a family package for TOML board files."""
    family_module = importlib.import_module(
        f"rugix_bsp.families.{family.name.replace('-', '_')}"
    )
    assert family_module.__file__ is not None
    family_dir = Path(family_module.__file__).resolve().parent
    boards_dir = family_dir / "boards"
    if not boards_dir.is_dir():
        return []

    boards: list[Board] = []
    for toml_file in sorted(boards_dir.glob("*.toml")):
        boards.append(_parse_board_toml(toml_file, family))
    return boards


def discover_all() -> list[Board]:
    """Discover all families and their boards."""
    families = discover_families()
    all_boards: list[Board] = []
    for family in families.values():
        all_boards.extend(discover_boards(family))
    return all_boards


def build_matrix(boards: list[Board]) -> list[tuple[Board, FamilyRelease]]:
    """Expand boards into (board, release) pairs."""
    matrix: list[tuple[Board, FamilyRelease]] = []
    for board in boards:
        for release_name, release in board.family.releases.items():
            if board.releases is None or release_name in board.releases:
                matrix.append((board, release))
    return matrix
