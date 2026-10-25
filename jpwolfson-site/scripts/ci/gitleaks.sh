#!/usr/bin/env bash
# Full-history secret scan with a version- and checksum-pinned gitleaks binary.
# Run from the repository root with a full (non-shallow) checkout.
set -euo pipefail
VERSION=8.30.1
SHA256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
tmp=$(mktemp -d)
curl -fsSL -o "$tmp/gitleaks.tgz" \
  "https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/gitleaks_${VERSION}_linux_x64.tar.gz"
echo "${SHA256}  $tmp/gitleaks.tgz" | sha256sum -c -
tar -xzf "$tmp/gitleaks.tgz" -C "$tmp" gitleaks
"$tmp/gitleaks" git --no-banner --redact --log-opts="--all" .
