#!/usr/bin/env bash
# Only for disposable GitHub-hosted Ubuntu 24.04 runners, never user machines.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_OS:-}" != Linux ]]; then
  echo 'This helper is restricted to Linux GitHub Actions runners.' >&2
  exit 1
fi
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]]
[[ $# -gt 0 ]]

# The Azure mirror took over 20 minutes to download dependencies in run
# 39940723230. Use the official HTTPS archive, retaining Ubuntu signature checks.
sudo tee /etc/apt/sources.list.d/ubuntu.sources >/dev/null <<'SOURCES'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu
Suites: noble noble-updates noble-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://security.ubuntu.com/ubuntu
Suites: noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES
apt_options=(-o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20)
sudo apt-get "${apt_options[@]}" update --error-on=any
sudo env DEBIAN_FRONTEND=noninteractive apt-get "${apt_options[@]}" install -y --no-install-recommends "$@"
