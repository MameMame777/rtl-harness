# Install the pinned Verible release (win64) into <harness>/.tools/verible after verifying its
# sha256 against rules/common/tool-versions.toml. Idempotent; -Force re-downloads.
#
#     .\scripts\install_verible.ps1 [-Force]
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Harness = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'lib\tool_versions.ps1')

$tv = Get-ToolVersions -Harness $Harness
$tag = $tv.verible.tag
$url = $tv.verible.win64_url
$sha = $tv.verible.win64_sha256
$toolsRoot = if ($env:RTL_HARNESS_TOOLS) { $env:RTL_HARNESS_TOOLS } else { Join-Path $Harness '.tools' }
$dest = Join-Path $toolsRoot 'verible'
$lint = Join-Path $dest 'verible-verilog-lint.exe'

if (-not $Force -and (Test-Path $lint)) {
    $have = (& $lint --version 2>$null | Select-Object -First 1)
    if ($have -and $have -like "*$tag*") {
        Write-Host "verible $tag already installed in $dest"
        return
    }
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("verible-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    $zip = Join-Path $tmp 'verible.zip'
    Write-Host "downloading verible $tag"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    $got = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLowerInvariant()
    if ($got -ne $sha.ToLowerInvariant()) {
        throw "sha256 mismatch for $url`n  expected $sha`n  got      $got"
    }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp 'x') -Force
    $exe = Get-ChildItem -Path (Join-Path $tmp 'x') -Recurse -Filter 'verible-verilog-lint.exe' | Select-Object -First 1
    if (-not $exe) { throw "verible-verilog-lint.exe not found in the archive" }
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item -Path (Join-Path $exe.DirectoryName '*') -Destination $dest -Recurse -Force
    Write-Host ("verible installed: " + (& $lint --version | Select-Object -First 1))
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
