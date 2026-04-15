"""NXP i.MX board family."""

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

_NXP_MANIFEST = (
    "https://raw.githubusercontent.com/nxp-imx/imx-manifest"
    "/imx-linux-scarthgap/imx-{version}.xml"
)

# Partition type UUID for Microsoft Basic Data — used for the FAT config
# partition so that Linux doesn't auto-mount it as an EFI System Partition.
_BASIC_DATA_TYPE = "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7"

_NXP_LOCAL_CONF = """\
IMX_DEFAULT_BSP = "nxp"
LICENSE_FLAGS_ACCEPTED += "commercial"
ACCEPT_FSL_EULA = "1"
PREFERRED_PROVIDER_virtual/kernel = "linux-imx"
PREFERRED_PROVIDER_u-boot = "u-boot-imx"
PREFERRED_PROVIDER_virtual/bootloader = "u-boot-imx"
"""

# Repos not needed for a minimal BSP build.
_MANIFEST_EXCLUDE = {
    "base",
    "meta-qt6",
    "meta-browser",
    "meta-security",
    "meta-timesys",
    "meta-virtualization",
    "meta-nxp-demo-experience",
    "meta-nxp-connectivity",
}

# Repos that contain multiple Yocto layers in subdirectories.
_NXP_LAYERS = {
    "poky": ["meta", "meta-poky", "meta-yocto-bsp"],
    "meta-openembedded": [
        "meta-oe",
        "meta-python",
        "meta-networking",
        "meta-multimedia",
        "meta-filesystems",
    ],
    "meta-arm": ["meta-arm", "meta-arm-toolchain"],
    "meta-imx": ["meta-imx-bsp", "meta-imx-sdk"],
}


def _nxp_release(version: str) -> FamilyRelease:
    return FamilyRelease(
        name=version,
        manifest_url=_NXP_MANIFEST.format(version=version),
        manifest_exclude=_MANIFEST_EXCLUDE,
        manifest_layers=_NXP_LAYERS,
        local_conf=_NXP_LOCAL_CONF,
    )


def _frdm_repos(version: str) -> dict[str, dict[str, str | dict[str, None]]]:
    return {
        "meta-imx-frdm": {
            "url": "https://github.com/nxp-imx-support/meta-imx-frdm.git",
            "branch": f"lf-{version}",
            "layers": {"meta-imx-bsp": None, "meta-imx-sdk": None},
        },
    }


@dataclass
class NxpImxFamily(BoardFamily):
    """NXP i.MX board family with metadata-driven blob offsets."""

    def resolve(self, metadata: dict[str, Any]) -> ResolvedConfig:
        seek = metadata.get("IMX_BOOT_SEEK", "32")
        return ResolvedConfig(
            disk_layout=DiskLayout(
                raw_blobs=[RawBlob("imx-boot", f"{seek}K")],
                partitions=[
                    Partition(
                        "config",
                        "64M",
                        type_uuid=_BASIC_DATA_TYPE,
                        filesystem="fat32",
                        root="config",
                    ),
                    Partition(
                        "boot-a",
                        "128M",
                        type_uuid=_BASIC_DATA_TYPE,
                        filesystem="fat32",
                        root="boot",
                    ),
                    Partition(
                        "boot-b",
                        "128M",
                        type_uuid=_BASIC_DATA_TYPE,
                        filesystem="fat32",
                    ),
                    Partition("system-a", root="system"),
                ],
            ),
            bundle_payloads=[
                BundlePayload(slot="boot", partition=2),
                BundlePayload(slot="system", partition=4),
            ],
        )


FAMILY = NxpImxFamily(
    name="nxp-imx",
    releases={
        "6.6.36-2.1.0": _nxp_release("6.6.36-2.1.0"),
        "6.6.52-2.2.0": _nxp_release("6.6.52-2.2.0"),
    },
    repo_groups={
        "frdm": {
            "6.6.36-2.1.0": _frdm_repos("6.6.36-2.1.0"),
        },
    },
    architecture="arm64",
    kernel_recipe="linux-imx",
    kas_targets=["virtual/kernel", "imx-boot", "rugix-boot-script"],
)
