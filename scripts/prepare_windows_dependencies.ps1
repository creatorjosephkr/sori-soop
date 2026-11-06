$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$folder = Join-Path $root 'build/prerequisites'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$packages = @(
    @{ Name = 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'; Url = 'https://go.microsoft.com/fwlink/?linkid=2124701' },
    @{ Name = 'vc_redist.x64.exe'; Url = 'https://aka.ms/vc14/vc_redist.x64.exe' }
)
$manifest = @()
foreach ($package in $packages) {
    $path = Join-Path $folder $package.Name
    Invoke-WebRequest -Uri $package.Url -OutFile $path -MaximumRetryCount 3 -RetryIntervalSec 3
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
        throw "Microsoft signature verification failed: $($package.Name)"
    }
    $version = (Get-Item -LiteralPath $path).VersionInfo
    $manifest += @{
        name = $package.Name; url = $package.Url; sha256 = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
        version = "$($version.FileMajorPart).$($version.FileMinorPart).$($version.FileBuildPart).$($version.FilePrivatePart)"
    }
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $folder 'manifest.json') -Encoding utf8
