# Rugix BSPs

Pre-built board support packages for [Rugix Bakery](https://github.com/rugix/rugix-bakery).

> [!WARNING]
> This project is **experimental and under active development**. The BSP format, tooling, and supported boards may change without notice. Use at your own risk.

## Overview

Rugix BSPs provides pre-built hardware support packages for use with [Rugix Bakery](https://github.com/rugix/rugix-bakery). Each BSP packages the kernel, device trees, firmware blobs, kernel modules, and boot scripts built from vendor Yocto BSP layers into a portable archive that Rugix Bakery can consume directly.

This decouples hardware enablement from the rootfs build — you can run Debian on an i.MX board without touching Yocto yourself.

## Supported Boards

| Board                   | Family   | SoC          |
| ----------------------- | -------- | ------------ |
| NXP FRDM-IMX91          | NXP i.MX | i.MX 91      |
| NXP i.MX 8M Plus EVK    | NXP i.MX | i.MX 8M Plus |
| CompuLab UCM-iMX8M-Plus | NXP i.MX | i.MX 8M Plus |
| Radxa Rock 5B           | Rockchip | RK3588       |
| Radxa Rock 5A           | Rockchip | RK3588S      |
| Radxa Zero 3            | Rockchip | RK3566       |

## Usage

### Building BSPs

```sh
just list                        # List available boards
just build nxp-imx91-frdm        # Build a single BSP
just build-all                   # Build all BSPs
```

Requires [uv](https://docs.astral.sh/uv/) and a container engine (Podman or Docker) for `kas-container`.

### Using a BSP with Rugix Bakery

Set `target = "bsp"` in your project and use a recipe to unpack the BSP archive:

```toml
# rugix-bakery.toml
[systems.my-device]
layer = "customized"
architecture = "arm64"
target = "bsp"
```

See `examples/imx91-frdm-project/` for a complete working example.

### BSP Archive Structure

Each BSP archive mirrors the Rugix Bakery layer structure:

```
<board>.bsp.tar.gz
├── bsp/
│   ├── rugix-bsp.toml          # Image layout, bundle mapping
│   ├── kas.yaml                # KAS config used for the build
│   ├── kas.lock.yaml           # Exact layer commits (source traceability)
│   ├── license-manifest.csv    # Licenses for all built recipes
│   └── licenses/               # Full license texts
├── roots/
│   ├── config/                 # Config partition overlay
│   └── system/                 # System root overlay (kernel, modules, DTBs, etc.)
├── artifacts/
│   └── firmware/               # Raw firmware blobs for image assembly
└── README.md
```

## How It Works

BSPs are built from vendor Yocto BSP layers using [KAS](https://kas.readthedocs.io/) inside a container. The Python tooling generates KAS configurations, runs the build, and extracts the relevant artifacts into a portable archive. The archive includes a KAS lockfile with exact commit hashes for full reproducibility and license compliance.

## Licensing

This project is licensed under either [MIT](LICENSE-MIT) or [Apache 2.0](LICENSE-APACHE) at your option.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in this project by you, as defined in the Apache 2.0 license, shall be dual licensed as above, without any additional terms or conditions.

**Note:** The BSP archives produced by this tooling contain binaries built from multiple open-source and proprietary components. Individual license terms are listed in each archive's `bsp/license-manifest.csv`. **It is the user's responsibility to review and comply with all applicable license terms.**

---

Made with ❤️ for OSS by [Silitics](https://www.silitics.com)
