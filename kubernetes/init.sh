#!/bin/bash

set -euo pipefail

KEYS_DIR="${BLCLI_KEYS_DIR:-$(pwd)/keys}"
PRIVATE_KEY_PATH="${KEYS_DIR}/argocd_github"
PUBLIC_KEY_PATH="${PRIVATE_KEY_PATH}.pub"

if ! command -v ssh-keygen >/dev/null 2>&1; then
    echo "[ERROR] ssh-keygen is not installed or not in PATH"
    exit 1
fi

mkdir -p "${KEYS_DIR}"

if [ ! -f "${PRIVATE_KEY_PATH}" ] || [ ! -f "${PUBLIC_KEY_PATH}" ]; then
    rm -f "${PRIVATE_KEY_PATH}" "${PUBLIC_KEY_PATH}"
    ssh-keygen -t ed25519 -N "" -f "${PRIVATE_KEY_PATH}" -C "argocd-github"
fi

chmod 700 "${KEYS_DIR}"
chmod 600 "${PRIVATE_KEY_PATH}"
chmod 644 "${PUBLIC_KEY_PATH}"

echo "[INFO] SSH private key: ${PRIVATE_KEY_PATH}"
echo "[INFO] SSH public key: ${PUBLIC_KEY_PATH}"
