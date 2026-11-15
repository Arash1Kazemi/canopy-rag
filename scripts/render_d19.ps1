# Renders the minutes D19 as an image, so the vision model has a "scanned page" to read.
# It needs nothing but Windows: it uses System.Drawing. Nothing is downloaded.
# Output: results\inputs\d19_clean.png and results\inputs\d19_degraded.png (turned 2 degrees and blurred).
param([string]$OutDir = "$PSScriptRoot\..\results\inputs")

Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$source = Join-Path $PSScriptRoot "..\case_study\documents\N6_bus_network_project\D19_meeting_minutes_2025-06-18.md"
$lines = Get-Content -LiteralPath $source -Encoding UTF8 | ForEach-Object { ($_ -replace '^#+\s*', '') -replace '\*\*', '' }

$width = 1240; $height = 1754   # an A4 page at 150 dots per inch
function New-Page {
    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.Clear([System.Drawing.Color]::White)
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
    $font = New-Object System.Drawing.Font('Arial', 26, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $y = 120
    foreach ($line in $lines) {
        if ($line.Trim() -eq '') { $y += 24; continue }
        $box = New-Object System.Drawing.RectangleF 100, $y, ($width - 200), 400
        $g.DrawString($line, $font, [System.Drawing.Brushes]::Black, $box)
        $y += $g.MeasureString($line, $font, ($width - 200)).Height + 8
    }
    $g.Dispose()
    return $bitmap
}

$clean = New-Page
$clean.Save((Join-Path $OutDir 'd19_clean.png'), [System.Drawing.Imaging.ImageFormat]::Png)

# Degraded copy: turn the page 2 degrees, then shrink to half size and back, which blurs it.
$turned = New-Object System.Drawing.Bitmap $width, $height
$g = [System.Drawing.Graphics]::FromImage($turned)
$g.Clear([System.Drawing.Color]::White)
$g.TranslateTransform($width / 2, $height / 2); $g.RotateTransform(2); $g.TranslateTransform(-$width / 2, -$height / 2)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.DrawImage($clean, 0, 0, $width, $height)
$g.Dispose()
$small = New-Object System.Drawing.Bitmap ([int]($width / 2)), ([int]($height / 2))
$g = [System.Drawing.Graphics]::FromImage($small); $g.DrawImage($turned, 0, 0, $small.Width, $small.Height); $g.Dispose()
$blurred = New-Object System.Drawing.Bitmap $width, $height
$g = [System.Drawing.Graphics]::FromImage($blurred); $g.DrawImage($small, 0, 0, $width, $height); $g.Dispose()
$blurred.Save((Join-Path $OutDir 'd19_degraded.png'), [System.Drawing.Imaging.ImageFormat]::Png)

foreach ($b in $clean, $turned, $small, $blurred) { $b.Dispose() }
Get-ChildItem $OutDir -Filter 'd19_*.png' | Select-Object Name, Length
