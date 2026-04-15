#!/bin/bash
set -euo pipefail

ORAS_VERSION="1.3.1"

if ! command -v oras &>/dev/null; then
    echo "Installing oras ${ORAS_VERSION}..."
    ARCH="$(uname -m)"
    case "${ARCH}" in
        x86_64)  ARCH="amd64" ;;
        aarch64) ARCH="arm64" ;;
    esac
    curl -fsSL "https://github.com/oras-project/oras/releases/download/v${ORAS_VERSION}/oras_${ORAS_VERSION}_linux_${ARCH}.tar.gz" \
        | tar xz -C /tmp oras
fi

ORAS="${ORAS:-/tmp/oras}"

BSP_REF="${RECIPE_PARAM_BSP_REGISTRY}/${RECIPE_PARAM_BSP_BOARD}:${RECIPE_PARAM_BSP_RELEASE}-${RECIPE_PARAM_BSP_VERSION}"

PULL_DIR="$(mktemp -d)"
trap 'rm -rf "${PULL_DIR}"' EXIT

echo "Pulling BSP from ${BSP_REF}..."
"${ORAS}" pull "${BSP_REF}" --output "${PULL_DIR}"

BSP_ARCHIVE="$(find "${PULL_DIR}" -name '*.bsp.tar.gz' | head -1)"
if [ -z "${BSP_ARCHIVE}" ]; then
    echo "No .bsp.tar.gz found in pulled artifacts"
    exit 1
fi

EXTRACT_DIR="$(mktemp -d)"
trap 'rm -rf "${PULL_DIR}" "${EXTRACT_DIR}"' EXIT
tar xzf "${BSP_ARCHIVE}" -C "${EXTRACT_DIR}"

mkdir -p "${RUGIX_LAYER_DIR}/roots" "${RUGIX_LAYER_DIR}/artifacts" "${RUGIX_LAYER_DIR}/bsp"
cp -a "${EXTRACT_DIR}/roots/"* "${RUGIX_LAYER_DIR}/roots/"
[ -d "${EXTRACT_DIR}/artifacts" ] && cp -a "${EXTRACT_DIR}/artifacts/"* "${RUGIX_LAYER_DIR}/artifacts/"
[ -d "${EXTRACT_DIR}/bsp" ] && cp -a "${EXTRACT_DIR}/bsp/"* "${RUGIX_LAYER_DIR}/bsp/"
