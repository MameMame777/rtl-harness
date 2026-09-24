# Install the pinned gitleaks release (windows x64) into <harness>/.tools/gitleaks after
# verifying its sha256 against rules/common/tool-versions.toml. Used by the pre-commit hook.
#
#     .\scripts\install_gitleaks.ps1 [-Force]
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Harness = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'lib\tool_versions.ps1')

$tv = Get-ToolVersions -Harness $Harness
$version = $tv.gitleaks.version
$url = $tv.gitleaks.windows_x64_url
$sha = $tv.gitleaks.windows_x64_sha256
$toolsRoot = if ($env:RTL_HARNESS_TOOLS) { $env:RTL_HARNESS_TOOLS } else { Join-Path $Harness '.tools' }
$dest = Join-Path $toolsRoot 'gitleaks'
$exe = Join-Path $dest 'gitleaks.exe'

if (-not $Force -and (Test-Path $exe)) {
    $have = (& $exe version 2>$null | Select-Object -First 1)
    if ($have -and $have -like "*$version*") {
        Write-Host "gitleaks $version already installed in $dest"
        return
    }
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("gitleaks-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    $zip = Join-Path $tmp 'gitleaks.zip'
    Write-Host "downloading gitleaks $version"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    $got = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLowerInvariant()
    if ($got -ne $sha.ToLowerInvariant()) {
        throw "sha256 mismatch for $url`n  expected $sha`n  got      $got"
    }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp 'x') -Force
    $found = Get-ChildItem -Path (Join-Path $tmp 'x') -Recurse -Filter 'gitleaks.exe' | Select-Object -First 1
    if (-not $found) { throw "gitleaks.exe not found in the archive" }
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item -Path $found.FullName -Destination $exe -Force
    Write-Host ("gitleaks installed: " + (& $exe version | Select-Object -First 1))
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
