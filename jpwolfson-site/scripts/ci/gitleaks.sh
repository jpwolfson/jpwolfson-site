#!/usr/bin/env bash
# Full-history secret scan with a version- and checksum-pinned gitleaks binary.
# Portable across Linux and macOS (x64 and arm64). Run from the repository root
# of a full (non-shallow) checkout; for a pre-publication gate, run it in a
# `git clone --mirror` so refs/pull/* are scanned too.
set -euo pipefail
VERSION=8.30.1
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)             ASSET=linux_x64;    SHA256=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
  Linux-aarch64|Linux-arm64) ASSET=linux_arm64; SHA256=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
  Darwin-arm64)             ASSET=darwin_arm64; SHA256=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
  Darwin-x86_64)            ASSET=darwin_x64;   SHA256=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
  *) echo "unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
esac
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/gitleaks.tgz" \
  "https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/gitleaks_${VERSION}_${ASSET}.tar.gz"
if command -v sha256sum >/dev/null 2>&1; then got=$(sha256sum "$tmp/gitleaks.tgz" | cut -d' ' -f1)
else got=$(shasum -a 256 "$tmp/gitleaks.tgz" | cut -d' ' -f1); fi
[ "$got" = "$SHA256" ] || { echo "checksum mismatch for gitleaks ${VERSION} ${ASSET}: $got"; exit 1; }
tar -xzf "$tmp/gitleaks.tgz" -C "$tmp" gitleaks
"$tmp/gitleaks" git --no-banner --redact --log-opts="--all" .
