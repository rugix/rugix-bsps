"""Rockchip board family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rugix_bsp.models import (
    BoardFamily,
    BundlePayload,
    DiskLayout,
    FamilyRelease,
    Partition,
    RawBlob,
    ResolvedConfig,
)

_ROCKCHIP_LOCAL_CONF = """\
LICENSE_FLAGS_ACCEPTED += "commercial"
"""

# Base repos for Rockchip Yocto builds (scarthgap).
_ROCKCHIP_REPOS_SCARTHGAP: dict[str, Any] = {
    "poky": {
        "url": "https://git.yoctoproject.org/poky",
        "branch": "scarthgap",
        "layers": {"meta": None, "meta-poky": None, "meta-yocto-bsp": None},
    },
    "meta-openembedded": {
        "url": "https://github.com/openembedded/meta-openembedded.git",
        "branch": "scarthgap",
        "layers": {
            "meta-oe": None,
            "meta-python": None,
            "meta-networking": None,
        },
    },
    "meta-rockchip": {
        "url": "https://git.yoctoproject.org/meta-rockchip",
        "branch": "scarthgap",
    },
}


@dataclass
class RockchipFamily(BoardFamily):
    """Rockchip board family with fixed bootloader offsets."""

    def resolve(self, metadata: dict[str, Any]) -> ResolvedConfig:
        return ResolvedConfig(
            disk_layout=DiskLayout(
                raw_blobs=[
                    RawBlob("idbloader.img", "32K"),
                    RawBlob("u-boot.itb", "8M"),
                ],
                partitions=[
                    Partition("config", "64M", filesystem="fat32", root="config"),
                    Partition("boot-a", "128M", filesystem="fat32", root="boot"),
                    Partition("boot-b", "128M", filesystem="fat32"),
                    Partition("system-a", root="system"),
                ],
            ),
            bundle_payloads=[
                BundlePayload(slot="boot", partition=2),
                BundlePayload(slot="system", partition=4),
            ],
        )


FAMILY = RockchipFamily(
    name="rockchip",
    releases={
        "scarthgap": FamilyRelease(
            name="scarthgap",
            repos=_ROCKCHIP_REPOS_SCARTHGAP,
            local_conf=_ROCKCHIP_LOCAL_CONF,
        ),
    },
    architecture="arm64",
    kernel_recipe="linux-yocto",
    kas_targets=["virtual/kernel", "virtual/bootloader", "rugix-boot-script"],
)
