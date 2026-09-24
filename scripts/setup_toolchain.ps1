# One-shot developer setup for rtl-harness on native Windows (MSYS2 ucrt64). Idempotent.
#
#     .\scripts\setup_toolchain.ps1 [-SkipPacman] [-SkipVenv] [-SkipSim] [-SkipTools]
#
# What it does:
#   1. pacman: verilator, gcc, python, pip, make, iverilog, perl (ucrt64)      [-SkipPacman]
#   2. .venv     : uv-managed CPython 3.12 with the [mcp,dev] extras (CLI / MCP / pre-commit)
#   3. .venv-sim : venv created FROM the ucrt64 python with the [sim] extra (cocotb, pytest);
#                  builds the static cocotb VPI library for Verilator (Windows workaround)
#   4. .tools    : Verible and gitleaks release binaries, sha256-verified
# Prerequisites: MSYS2 installed (any directory; set MSYS2_ROOT if it is not on PATH), uv, git.
[CmdletBinding()]
param(
    [switch]$SkipPacman,
    [switch]$SkipVenv,
    [switch]$SkipSim,
    [switch]$SkipTools
)

$ErrorActionPreference = 'Stop'
$Harness = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'lib\tool_versions.ps1')
Set-Location $Harness

function Step($n, $msg) { Write-Host "== [$n] $msg ==" -ForegroundColor Cyan }

# --- MSYS2 -----------------------------------------------------------------------------
$root = $null
try { $root = Resolve-Msys2Root } catch { }
if (-not $root -and -not $SkipPacman) {
    # verilator may not be installed yet: locate MSYS2 through pacman instead
    if ($env:MSYS2_ROOT -and (Test-Path (Join-Path $env:MSYS2_ROOT 'usr\bin\pacman.exe'))) {
        $root = (Resolve-Path $env:MSYS2_ROOT).Path
    } else {
        $p = Get-Command pacman -ErrorAction SilentlyContinue
        if ($p -and $p.Source) { $root = Split-Path -Parent (Split-Path -Parent $p.Source) }
    }
}
if (-not $root) { throw "MSYS2 not found. Install it from https://www.msys2.org and set MSYS2_ROOT." }
$env:MSYS2_ROOT = $root
$ucrt = Join-Path $root 'ucrt64\bin'
$ucrtPy = Join-Path $ucrt 'python.exe'
$env:PATH = "$ucrt;$(Join-Path $root 'usr\bin');" + $env:PATH
Write-Host "MSYS2_ROOT = $root"

if (-not $SkipPacman) {
    Step 1 'pacman ucrt64 packages'
    $pacman = Join-Path $root 'usr\bin\pacman.exe'
    & $pacman -S --needed --noconfirm `
        mingw-w64-ucrt-x86_64-verilator `
        mingw-w64-ucrt-x86_64-gcc `
        mingw-w64-ucrt-x86_64-python `
        mingw-w64-ucrt-x86_64-python-pip `
        mingw-w64-ucrt-x86_64-make `
        mingw-w64-ucrt-x86_64-iverilog `
        perl
    if ($LASTEXITCODE -ne 0) { throw "pacman failed ($LASTEXITCODE)" }
}

# --- .venv (CLI / MCP / dev) --------------------------------------------------------------
if (-not $SkipVenv) {
    Step 2 '.venv: uv sync --extra mcp --extra dev (CPython 3.12)'
    $tv = Get-ToolVersions -Harness $Harness
    $env:UV_LINK_MODE = 'copy'
    uv sync --python $tv.python.core --extra mcp --extra dev
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed ($LASTEXITCODE)" }
}

# --- .venv-sim (cocotb on the ucrt64 python) ---------------------------------------------
if (-not $SkipSim) {
    Step 3 '.venv-sim: cocotb venv from the ucrt64 python'
    if (-not (Test-Path $ucrtPy)) { throw "ucrt64 python not found at $ucrtPy (run without -SkipPacman)" }
    $venv = Join-Path $Harness '.venv-sim'
    $venvPy = Join-Path $venv 'bin\python.exe'
    if (-not (Test-Path $venvPy)) {
        & $ucrtPy -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw "venv creation failed ($LASTEXITCODE)" }
    }
    # cocotb 2.0.1 declares python<3.14 but runs fine on the ucrt64 3.14 (proven on 53 blocks).
    $env:COCOTB_IGNORE_PYTHON_REQUIRES = '1'
    & $venvPy -m pip install --no-input --quiet --upgrade pip
    & $venvPy -m pip install --no-input -e ".[sim]"
    if ($LASTEXITCODE -ne 0) { throw "pip install into .venv-sim failed ($LASTEXITCODE)" }
    $bootstrap = Join-Path $Harness 'tb\harness_tb\bootstrap_vpi.py'
    if (Test-Path $bootstrap) {
        Write-Host 'building the static cocotb VPI library for Verilator (first time only)'
        & $venvPy $bootstrap
        if ($LASTEXITCODE -ne 0) { throw "bootstrap_vpi failed ($LASTEXITCODE)" }
    } else {
        Write-Warning "tb/harness_tb/bootstrap_vpi.py not found; VPI library not built"
    }
}

# --- release binaries ----------------------------------------------------------------------
if (-not $SkipTools) {
    Step 4 'Verible and gitleaks (sha256-verified)'
    & (Join-Path $PSScriptRoot 'install_verible.ps1')
    & (Join-Path $PSScriptRoot 'install_gitleaks.ps1')
}

Write-Host ''
Write-Host 'toolchain ready:' -ForegroundColor Green
Write-Host "  MSYS2_ROOT : $root"
Write-Host "  .venv      : $(Join-Path $Harness '.venv')  (uv run --project . rtl-harness ...)"
Write-Host "  .venv-sim  : $(Join-Path $Harness '.venv-sim')  (cocotb / pytest)"
Write-Host "  .tools     : $(Join-Path $Harness '.tools')  (verible, gitleaks)"
Write-Host 'next: uv run --project . rtl-harness doctor'
