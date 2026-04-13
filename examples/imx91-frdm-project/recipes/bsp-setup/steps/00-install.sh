#!/bin/bash
set -euo pipefail

BSP_ARCHIVE="${RECIPE_DIR}/files/nxp-imx91-frdm.bsp.tar.gz"
BSP_DIR="$(mktemp -d)"
trap 'rm -rf "${BSP_DIR}"' EXIT

tar xzf "${BSP_ARCHIVE}" -C "${BSP_DIR}" --strip-components=1

# The BSP archive mirrors the layer structure. Just overlay it.
mkdir -p "${RUGIX_LAYER_DIR}/roots" "${RUGIX_LAYER_DIR}/artifacts" "${RUGIX_LAYER_DIR}/bsp"
cp -a "${BSP_DIR}/roots/"* "${RUGIX_LAYER_DIR}/roots/"
cp -a "${BSP_DIR}/artifacts/"* "${RUGIX_LAYER_DIR}/artifacts/"
cp -a "${BSP_DIR}/bsp/"* "${RUGIX_LAYER_DIR}/bsp/"

# Run depmod for installed kernel modules.
for kver_dir in "${RUGIX_ROOT_DIR}/usr/lib/modules/"*/; do
    [ -d "${kver_dir}" ] || continue
    kver="$(basename "${kver_dir}")"
    depmod -a -b "${RUGIX_ROOT_DIR}" "${kver}" || true
done
