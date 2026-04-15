"""Data models for BSP definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class RawBlob:
    """Firmware blob written at a fixed disk offset."""

    deploy_file: str
    offset: str


@dataclass
class Partition:
    """Partition in the BSP disk layout."""

    name: str
    size: str | None = None
    type_uuid: str | None = None
    filesystem: str = "ext4"
    root: str | None = None


@dataclass
class DiskLayout:
    """Complete disk layout for a board."""

    table_type: str = "gpt"
    raw_blobs: list[RawBlob] = field(default_factory=list)
    partitions: list[Partition] = field(default_factory=list)


@dataclass
class BundlePayload:
    """Maps a partition or file to an update slot."""

    slot: str
    partition: int | None = None
    file: str | None = None


@dataclass
class ResolvedConfig:
    """Build-output-dependent configuration, produced by BoardFamily.resolve().

    Contains everything that may depend on Yocto build metadata (e.g.,
    IMX_BOOT_SEEK, KERNEL_IMAGETYPE) rather than being known statically.
    """

    disk_layout: DiskLayout = field(default_factory=DiskLayout)
    system_toml: str = ""
    bootstrapping_toml: str = ""
    bundle_payloads: list[BundlePayload] = field(default_factory=list)


@dataclass
class FamilyRelease:
    """A versioned Yocto layer stack for a family.

    Repos can be specified inline or derived from a repo manifest URL.
    When *manifest_url* is set, repos are fetched and parsed lazily on
    first access via resolve_repos().
    """

    name: str
    repos: dict[str, Any] = field(default_factory=dict)
    manifest_url: str = ""
    manifest_exclude: set[str] = field(default_factory=set)
    manifest_layers: dict[str, list[str]] = field(default_factory=dict)
    local_conf: str = ""
    kas_targets: list[str] | None = None
    _resolved_repos: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def resolve_repos(self) -> dict[str, Any]:
        """Return repos, fetching from manifest URL if needed."""
        if self._resolved_repos is not None:
            return self._resolved_repos

        if self.repos:
            self._resolved_repos = dict(self.repos)
        elif self.manifest_url:
            from rugix_bsp.kas.manifest import parse_repo_manifest

            self._resolved_repos = parse_repo_manifest(
                self.manifest_url,
                exclude=self.manifest_exclude,
                layers=self.manifest_layers or None,
            )
        else:
            self._resolved_repos = {}

        return self._resolved_repos


@dataclass
class BoardFamily:
    """Shared configuration for a family of boards.

    Holds build inputs (repos, machine config, targets) that are known
    statically. Build-output-dependent config (disk layout, blob offsets)
    is produced by resolve(), which families override.
    """

    name: str
    releases: dict[str, FamilyRelease]
    architecture: str = "arm64"
    kas_distro: str = "poky"
    kas_targets: list[str] = field(default_factory=lambda: ["virtual/kernel"])
    kas_container_distro: str = "debian-bookworm"
    kernel_recipe: str = "linux-yocto"
    local_conf: str = ""
    repo_groups: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def resolve(self, metadata: dict[str, Any]) -> ResolvedConfig:
        """Derive build-output-dependent config from Yocto metadata.

        Families override this to compute values like raw blob offsets
        from build variables (e.g., IMX_BOOT_SEEK). The default returns
        an empty config.
        """
        return ResolvedConfig()


@dataclass
class Board:
    """A specific board within a family."""

    name: str
    machine: str
    family: BoardFamily
    description: str = ""
    vendor: str = ""
    support: Literal["community", "tested", "official"] = "community"
    releases: list[str] | None = None
    repo_groups: list[str] = field(default_factory=list)
    extra_repos: dict[str, Any] = field(default_factory=dict)
    release_repos: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra_local_conf: str = ""
    kas_container_distro: str | None = None

    def repos_for_release(self, release_name: str) -> dict[str, Any]:
        """Return extra repos for a specific release."""
        repos: dict[str, Any] = {}
        for group in self.repo_groups:
            group_releases = self.family.repo_groups.get(group, {})
            repos.update(group_releases.get(release_name, {}))
        repos.update(self.extra_repos)
        repos.update(self.release_repos.get(release_name, {}))
        return repos
