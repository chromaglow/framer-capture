$ErrorActionPreference = 'Stop'

Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Ensuring uv is available..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $paths = @("$env:LOCALAPPDATA\Microsoft\WinGet\Links", "$env:USERPROFILE\.local\bin")
    foreach ($p in $paths) {
        if (Test-Path $p) {
            $env:PATH = "$p;$env:PATH"
        }
    }

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "Installing uv via WinGet..."
        winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
        $env:PATH = "$($paths[0]);$($paths[1]);$env:PATH"
    }

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv not found"
    }
}

Write-Host "Installing Python 3.12 and syncing dependencies..."
uv python install 3.12
if ($LASTEXITCODE -ne 0) { throw "uv python install failed" }
uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

Write-Host "Running make_assets.py..."
uv run python scripts/make_assets.py
if ($LASTEXITCODE -ne 0) { throw "make_assets.py failed" }

Write-Host "Running pytest..."
uv run pytest
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Host "Running PyInstaller..."
uv run pyinstaller --noconfirm --clean framer.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "Preparing release folder..."
if (-not (Test-Path "release")) {
    New-Item -ItemType Directory -Path "release" | Out-Null
}
Copy-Item "dist\Framer.exe" "release\Framer.exe" -Force

Write-Host "Running self-test..."
$proc = Start-Process -FilePath ".\release\Framer.exe" -ArgumentList "--self-test" -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ne 0) {
    $log = Get-Content "$env:APPDATA\Framer\selftest.txt" -ErrorAction SilentlyContinue
    Write-Host "Self-test failed. Log content:"
    Write-Host $log
    throw "self-test failed"
}

$file = Get-Item "release\Framer.exe"
$sizeMB = [math]::Round($file.Length / 1MB, 2)
Write-Host "Build OK: release\Framer.exe ($sizeMB MB)"