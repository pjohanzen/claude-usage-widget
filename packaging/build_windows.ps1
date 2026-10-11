# Build the portable Windows app on a Windows machine. Run from the project root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# Output: build\ClaudeUsageWidget-windows-portable.zip (unzip anywhere and run ClaudeUsageWidget.exe)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]" pyinstaller

& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check src tests packaging
& .\.venv\Scripts\python.exe -m mypy

& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name ClaudeUsageWidget `
    --paths src --distpath build\dist --workpath build\pyinstaller --specpath build packaging\launcher.py

$exe = Resolve-Path "build\dist\ClaudeUsageWidget\ClaudeUsageWidget.exe"
$proc = Start-Process -FilePath $exe -ArgumentList "--version" -Wait -PassThru
if ($proc.ExitCode -ne 0) { throw "Packaged app exited with code $($proc.ExitCode)" }

Compress-Archive -Path build\dist\ClaudeUsageWidget -DestinationPath build\ClaudeUsageWidget-windows-portable.zip -Force
Write-Host "Built build\ClaudeUsageWidget-windows-portable.zip"
