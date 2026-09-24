#!/usr/bin/env bash
# Developer setup for rtl-harness on Linux (outside the CI container). Idempotent.
#
#     bash scripts/setup_toolchain.sh
#
# Expects verilator (5.048) and a C++ toolchain to be installed by the distribution or from
# source; installs Verible and gitleaks (sha256-verified) into .tools and creates ONE venv
# (.venv, uv-managed CPython 3.12) with the sim, mcp and dev extras. On Linux cocotb ships
# its VPI libraries in the wheel, so no bootstrap step is needed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v uv >/dev/null || { echo "uv is required (https://docs.astral.sh/uv/)"; exit 1; }
command -v verilator >/dev/null || echo "warning: verilator not on PATH; run_sim will fail until it is installed"

PY=$(python3 - <<'PY'
import tomllib
print(tomllib.load(open("rules/common/tool-versions.toml", "rb"))["python"]["core"])
PY
)
echo "== .venv: uv sync (python $PY) =="
UV_LINK_MODE=copy uv sync --python "$PY" --extra sim --extra mcp --extra dev

echo "== verible =="
bash scripts/install_verible.sh
echo "== gitleaks =="
bash scripts/ci/install_gitleaks.sh >/dev/null
echo
echo "toolchain ready. next: uv run --project . rtl-harness doctor"
