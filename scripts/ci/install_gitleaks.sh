#!/usr/bin/env bash
# Install the pinned gitleaks release (Linux x64) into .tools/gitleaks after verifying its
# sha256 against rules/common/tool-versions.toml. Adds the directory to GITHUB_PATH when run
# inside GitHub Actions, otherwise prints the path to export.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TV="$ROOT/rules/common/tool-versions.toml"
DEST="$ROOT/.tools/gitleaks"

read -r VERSION URL SHA < <(python3 - "$TV" <<'PY'
import sys, tomllib
t = tomllib.load(open(sys.argv[1], "rb"))["gitleaks"]
print(t["version"], t["linux_x64_url"], t["linux_x64_sha256"])
PY
)

if [ -x "$DEST/gitleaks" ] && "$DEST/gitleaks" version 2>/dev/null | grep -q "$VERSION"; then
  echo "gitleaks $VERSION already installed in $DEST"
else
  mkdir -p "$DEST"
  tmp="$(mktemp -d)"
  echo "downloading gitleaks $VERSION"
  curl -fsSL --proto '=https' --tlsv1.2 -o "$tmp/gitleaks.tar.gz" "$URL"
  echo "$SHA  $tmp/gitleaks.tar.gz" | sha256sum -c -
  tar -xzf "$tmp/gitleaks.tar.gz" -C "$DEST" gitleaks
  rm -rf "$tmp"
  echo "gitleaks $VERSION installed in $DEST"
fi

if [ -n "${GITHUB_PATH:-}" ]; then
  echo "$DEST" >> "$GITHUB_PATH"
else
  echo "export PATH=\"$DEST:\$PATH\""
fi
