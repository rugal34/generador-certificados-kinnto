$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$env:STREAMLIT_SERVER_HEADLESS = "true"
$env:STREAMLIT_SERVER_ADDRESS = "127.0.0.1"
$env:STREAMLIT_SERVER_PORT = "8501"

$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$outLog = Join-Path $logDir "streamlit.out.log"
$errLog = Join-Path $logDir "streamlit.err.log"

if (-not (Test-Path $python)) {
    throw "No se encontro el entorno local. Ejecuta: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $python -m streamlit run app.py `
    --server.address 127.0.0.1 `
    --server.port 8501 `
    --server.headless true `
    --browser.gatherUsageStats false
