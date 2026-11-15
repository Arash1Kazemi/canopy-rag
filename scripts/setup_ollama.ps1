# Downloads the standalone Ollama for Windows and unpacks it. Run it only after you approved the download.
#   File:   ollama-windows-amd64.zip  (about 1586 MB, release v0.40.11)
#   Source: https://github.com/ollama/ollama/releases
# It checks the file against the published sha256sum.txt before unpacking, and stops if they differ.
param(
    [string]$Version = "v0.40.11",
    [string]$Target = "E:\UNI\Semesterr 7\AI-Engineering\ollama"
)
$base = "https://github.com/ollama/ollama/releases/download/$Version"
$work = Join-Path $env:TEMP "ollama-download"
New-Item -ItemType Directory -Force -Path $work, $Target | Out-Null

Invoke-WebRequest -Uri "$base/sha256sum.txt" -OutFile (Join-Path $work "sha256sum.txt")
$line = Get-Content (Join-Path $work "sha256sum.txt") | Where-Object { $_ -match 'ollama-windows-amd64\.zip$' } | Select-Object -First 1
if (-not $line) { throw "ollama-windows-amd64.zip is not in sha256sum.txt" }
$expected = ($line -split '\s+')[0].ToLower()

$zip = Join-Path $work "ollama-windows-amd64.zip"
Invoke-WebRequest -Uri "$base/ollama-windows-amd64.zip" -OutFile $zip
$actual = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
if ($actual -ne $expected) { throw "checksum mismatch: expected $expected but got $actual. Nothing was unpacked." }
"checksum ok: $actual"

Expand-Archive -Path $zip -DestinationPath $Target -Force
Remove-Item $work -Recurse -Force
& (Join-Path $Target "ollama.exe") --version
