#!/bin/bash
set -euo pipefail

for kver_dir in /usr/lib/modules/*/; do
    [ -d "${kver_dir}" ] || continue
    kver="$(basename "${kver_dir}")"
    depmod -a "${kver}" || true
done
