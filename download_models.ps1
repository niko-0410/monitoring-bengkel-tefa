param(
    [string]$ReleaseTag = "models-v1"
)

$Repo = "niko-0410/monitoring-bengkel-tefa"
$BaseUrl = "https://github.com/$Repo/releases/download/$ReleaseTag"
$ModelsDir = Join-Path $PSScriptRoot "models"
$Files = @(
    "apd_custom_best.pt",
    "ppe_6class.onnx",
    "ppe_6class.pt"
)

if (!(Test-Path $ModelsDir)) { New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null }

foreach ($file in $Files) {
    $url = "$BaseUrl/$file"
    $out = Join-Path $ModelsDir $file
    Write-Host "Downloading $file ..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        Write-Host "  OK -> $out"
    } catch {
        Write-Host "  GAGAL: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`nSelesai. Jalankan ulang aplikasi."