#!/bin/bash
# Generates the SSH key pair that ArgoCD uses to read the GitOps repository.
#
# The private key must never be committed. By default it is written outside the
# kubernetes repository, to <workspace>/keys (the parent directory of this
# repository). Set BLCLI_KEYS_DIR to choose another directory. The key directory
# gets a ".gitignore" that ignores everything in it, and the kubernetes repository
# gets a ".gitignore" for key material, so neither ends up in git even if the
# directory sits inside a repository.

set -euo pipefail

KUBERNETES_DIR="${BLCLI_KUBERNETES_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
KEYS_DIR="${BLCLI_KEYS_DIR:-$(dirname "${KUBERNETES_DIR}")/keys}"
# Earlier versions wrote the key to <kubernetes>/keys. Reuse it rather than creating a new one.
if [ -z "${BLCLI_KEYS_DIR:-}" ] && [ ! -f "${KEYS_DIR}/argocd_github" ] && [ -f "${KUBERNETES_DIR}/keys/argocd_github" ]; then
    echo "[WARN] Using the existing key in ${KUBERNETES_DIR}/keys. Move that directory to ${KEYS_DIR} to keep it out of the repository."
    KEYS_DIR="${KUBERNETES_DIR}/keys"
fi
PRIVATE_KEY_PATH="${KEYS_DIR}/argocd_github"
PUBLIC_KEY_PATH="${PRIVATE_KEY_PATH}.pub"

if ! command -v ssh-keygen >/dev/null 2>&1; then
    echo "[ERROR] ssh-keygen is not installed or not in PATH"
    exit 1
fi

# Keep key material out of the kubernetes repository (blcli `apply init-repos` runs `git add .`).
GITIGNORE="${KUBERNETES_DIR}/.gitignore"
for pattern in "keys/" "*.pem" "*.key" "id_rsa" "id_ecdsa" "id_ed25519" "*_rsa" "*_ecdsa" "*_ed25519" "argocd_github"; do
    if ! grep -qxF -- "${pattern}" "${GITIGNORE}" 2>/dev/null; then
        printf '%s\n' "${pattern}" >> "${GITIGNORE}"
    fi
done

umask 077
mkdir -p "${KEYS_DIR}"
chmod 700 "${KEYS_DIR}"
# Ignore every file in the key directory, wherever it is.
printf '*\n' > "${KEYS_DIR}/.gitignore"

case "$(cd "${KEYS_DIR}" && pwd)/" in
    "${KUBERNETES_DIR}/"*)
        echo "[WARN] ${KEYS_DIR} is inside the kubernetes repository. It is git-ignored, but keep keys outside the repository (set BLCLI_KEYS_DIR)."
        ;;
esac

if [ ! -f "${PRIVATE_KEY_PATH}" ] || [ ! -f "${PUBLIC_KEY_PATH}" ]; then
    rm -f "${PRIVATE_KEY_PATH}" "${PUBLIC_KEY_PATH}"
    ssh-keygen -q -t ed25519 -N "" -f "${PRIVATE_KEY_PATH}" -C "argocd-github"
fi

chmod 600 "${PRIVATE_KEY_PATH}"
chmod 644 "${PUBLIC_KEY_PATH}"

echo "[INFO] SSH private key: ${PRIVATE_KEY_PATH} (do not commit)"
echo "[INFO] SSH public key: ${PUBLIC_KEY_PATH}"
echo "[INFO] Add the public key to the GitOps repository as a read-only deploy key (leave \"Allow write access\" unchecked)."
