# Shared helpers for the PowerShell setup scripts. Dot-source this file.
#
#   Get-ToolVersions -Harness <root>  -> nested hashtable of rules/common/tool-versions.toml
#   Resolve-Msys2Root                 -> MSYS2 install dir (env MSYS2_ROOT -> verilator on PATH -> probe)
#
# The TOML reader is deliberately minimal: tool-versions.toml only uses [section] headers and
# key = "string" lines, which is all this needs. No absolute paths are committed anywhere.

function Get-ToolVersions {
    param([Parameter(Mandatory = $true)][string]$Harness)
    $path = Join-Path $Harness 'rules\common\tool-versions.toml'
    if (-not (Test-Path $path)) { throw "tool-versions.toml not found at $path" }
    $result = @{}
    $section = $null
    foreach ($line in Get-Content $path) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        if ($t -match '^\[([A-Za-z0-9_-]+)\]$') {
            $section = $Matches[1]
            if (-not $result.ContainsKey($section)) { $result[$section] = @{} }
            continue
        }
        if ($section -and $t -match '^([A-Za-z0-9_]+)\s*=\s*"([^"]*)"') {
            $result[$section][$Matches[1]] = $Matches[2]
        }
    }
    return $result
}

function Resolve-Msys2Root {
    # 1. explicit override
    if ($env:MSYS2_ROOT -and (Test-Path (Join-Path $env:MSYS2_ROOT 'ucrt64\bin\verilator_bin.exe'))) {
        return (Resolve-Path $env:MSYS2_ROOT).Path
    }
    # 2. derive from a verilator on PATH (works for a non-standard install dir)
    $v = Get-Command verilator -ErrorAction SilentlyContinue
    if ($v -and $v.Source) {
        $root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $v.Source))
        if (Test-Path (Join-Path $root 'ucrt64\bin\verilator_bin.exe')) { return $root }
    }
    # 3. probe the standard MSYS2 install locations (not user data)
    $cands = @('C:\msys64', 'C:\msys2', 'C:\tools\msys64')  # hygiene-ok: well-known install roots
    if ($env:LOCALAPPDATA) { $cands += (Join-Path $env:LOCALAPPDATA 'msys64') }
    foreach ($c in $cands) {
        if (Test-Path (Join-Path $c 'ucrt64\bin\verilator_bin.exe')) { return $c }
    }
    throw "MSYS2 ucrt64 with Verilator not found. Install MSYS2 (https://www.msys2.org), run pacman -S mingw-w64-ucrt-x86_64-verilator, then set MSYS2_ROOT to the install dir."
}
