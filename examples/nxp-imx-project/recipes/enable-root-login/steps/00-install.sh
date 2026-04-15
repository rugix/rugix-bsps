#!/bin/bash
set -euo pipefail

# Remove root password.
passwd -d root

# Allow root login without password on serial console.
sed -i 's|^root:[^:]*:|root::|' "${RUGIX_ROOT_DIR}/etc/shadow"

# Permit root login on TTY (for getty/serial console).
if [ -f "${RUGIX_ROOT_DIR}/etc/securetty" ]; then
    grep -q "ttyLP0" "${RUGIX_ROOT_DIR}/etc/securetty" || echo "ttyLP0" >> "${RUGIX_ROOT_DIR}/etc/securetty"
fi
