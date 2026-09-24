#!/usr/bin/env bash
# Install the pinned Verible release (linux static x86_64) into .tools/verible after verifying
# its sha256 against rules/common/tool-versions.toml. Idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${RTL_HARNESS_TOOLS:-$ROOT/.tools}/verible"

read -r TAG URL SHA < <(python3 - "$ROOT/rules/common/tool-versions.toml" <<'PY'
import sys, tomllib
t = tomllib.load(open(sys.argv[1], "rb"))["verible"]
print(t["tag"], t["linux_x86_64_url"], t["linux_x86_64_sha256"])
PY
)

if [ -x "$DEST/bin/verible-verilog-lint" ] && "$DEST/bin/verible-verilog-lint" --version 2>/dev/null | head -1 | grep -q "$TAG"; then
  echo "verible $TAG already installed in $DEST"
  exit 0
fi

tmp="$(mktemp -d)"
echo "downloading verible $TAG"
curl -fsSL --proto '=https' --tlsv1.2 -o "$tmp/verible.tar.gz" "$URL"
echo "$SHA  $tmp/verible.tar.gz" | sha256sum -c -
rm -rf "$DEST"; mkdir -p "$DEST"
tar -xzf "$tmp/verible.tar.gz" -C "$DEST" --strip-components=1
rm -rf "$tmp"
echo "verible installed: $("$DEST/bin/verible-verilog-lint" --version | head -1)"
