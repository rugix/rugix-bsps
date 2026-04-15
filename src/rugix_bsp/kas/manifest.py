"""Google repo manifest XML to Kas repos conversion."""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_repo_manifest(
    source: str | Path,
    *,
    exclude: set[str] | None = None,
    layers: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Parse a Google repo manifest into Kas repo entries.

    *source* can be a local file path or an HTTP(S) URL. Each <project>
    becomes a Kas repo entry with url and commit/branch/tag. Projects are
    keyed by the last component of their path (e.g., "sources/meta-freescale"
    becomes "meta-freescale").

    Use *exclude* to skip projects by key. Use *layers* to declare which
    sub-layers a multi-layer repo contains (e.g., poky has meta, meta-poky).
    """
    source_str = str(source)
    if source_str.startswith(("http://", "https://")):
        result = subprocess.run(
            ["curl", "-fsSL", source_str],
            capture_output=True,
            check=True,
        )
        root = ET.fromstring(result.stdout)
    else:
        tree = ET.parse(source_str)
        root = tree.getroot()

    repos = _extract_repos(root, exclude or set())

    if layers:
        for repo_key, layer_list in layers.items():
            if repo_key in repos:
                repos[repo_key]["layers"] = {name: None for name in layer_list}

    return repos


def _extract_repos(root: ET.Element, skip: set[str]) -> dict[str, Any]:
    remotes: dict[str, str] = {}
    for remote_el in root.findall("remote"):
        name = remote_el.get("name", "")
        fetch = remote_el.get("fetch", "").rstrip("/")
        remotes[name] = fetch

    default_el = root.find("default")
    default_remote = default_el.get("remote", "") if default_el is not None else ""
    default_revision = default_el.get("revision", "") if default_el is not None else ""

    repos: dict[str, Any] = {}
    for project_el in root.findall("project"):
        project_name = project_el.get("name", "")
        remote_name = project_el.get("remote", default_remote)
        revision = project_el.get("revision", default_revision)
        path = project_el.get("path", project_name)

        repo_key = path.rsplit("/", 1)[-1]
        if repo_key in skip:
            continue

        fetch_url = remotes.get(remote_name, "")
        url = f"{fetch_url}/{project_name}" if fetch_url else project_name

        entry: dict[str, Any] = {"url": url}
        _classify_revision(revision, entry)
        repos[repo_key] = entry

    return repos


def _classify_revision(revision: str, entry: dict[str, Any]) -> None:
    """Classify a revision string as commit, tag, or branch."""
    if not revision:
        return
    if revision.startswith("refs/tags/"):
        entry["tag"] = revision.removeprefix("refs/tags/")
    elif _is_commit_hash(revision):
        entry["commit"] = revision
    else:
        entry["branch"] = revision


def _is_commit_hash(value: str) -> bool:
    return len(value) == 40 and all(c in "0123456789abcdef" for c in value)
