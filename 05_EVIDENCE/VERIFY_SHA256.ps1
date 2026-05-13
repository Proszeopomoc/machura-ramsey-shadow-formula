$Root = Split-Path $PSScriptRoot -Parent
$Manifest = Join-Path $PSScriptRoot "MANIFEST_SHA256.txt"

if (-not (Test-Path $Manifest)) {
    throw "Manifest not found: $Manifest"
}

$Lines = Get-Content $Manifest | Where-Object { $_.Trim() -ne "" }
$Ok = $true

foreach ($line in $Lines) {
    $parts = $line -split "  ", 2
    $expected = $parts[0].Trim()
    $rel = $parts[1].Trim()
    $path = Join-Path $Root $rel

    if (-not (Test-Path $path)) {
        Write-Host "MISSING: $rel" -ForegroundColor Red
        $Ok = $false
        continue
    }

    $actual = (Get-FileHash $path -Algorithm SHA256).Hash

    if ($actual -ne $expected) {
        Write-Host "HASH MISMATCH: $rel" -ForegroundColor Red
        Write-Host "expected: $expected"
        Write-Host "actual:   $actual"
        $Ok = $false
    } else {
        Write-Host "OK: $rel" -ForegroundColor Green
    }
}

if ($Ok) {
    Write-Host "ALL HASHES OK" -ForegroundColor Green
} else {
    throw "HASH VERIFICATION FAILED"
}
