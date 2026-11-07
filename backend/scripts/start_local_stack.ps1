$ErrorActionPreference = "Stop"
$Backend = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Llama = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
$Logs = Join-Path $Backend "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Test-LocalPort([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

if (-not (Test-LocalPort 8088)) {
    if (-not (Test-Path $Llama)) { throw "llama-server.exe not found: $Llama" }
    Start-Process -FilePath $Llama -WorkingDirectory $Backend -ArgumentList @(
        "-hf", "Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0",
        "--embedding", "--pooling", "last", "--embd-normalize", "2",
        "--host", "127.0.0.1", "--port", "8088",
        "--n-gpu-layers", "0", "--threads", "4", "--threads-batch", "4",
        "-b", "512", "-ub", "512", "-np", "1"
    ) -RedirectStandardOutput (Join-Path $Logs "qwen-embedding.log") -RedirectStandardError (Join-Path $Logs "qwen-embedding-error.log") -WindowStyle Hidden
}

$Ready = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8088/health" -TimeoutSec 2
        if ($Health.status -eq "ok") { $Ready = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $Ready) { throw "Local Qwen embedding server did not become healthy on port 8088." }

if (-not (Test-LocalPort 8018)) {
    Start-Process -FilePath $Python -WorkingDirectory $Backend -ArgumentList @(
        "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8018"
    ) -RedirectStandardOutput (Join-Path $Logs "api.log") -RedirectStandardError (Join-Path $Logs "api-error.log") -WindowStyle Hidden
}

$Worker = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object {
        $_.CommandLine -match "app\.workers\.runner" -and
        $_.ExecutablePath -like ($Backend + "*")
    }
if (-not $Worker) {
    Start-Process -FilePath $Python -WorkingDirectory $Backend -ArgumentList @("-m", "app.workers.runner") -RedirectStandardOutput (Join-Path $Logs "worker.log") -RedirectStandardError (Join-Path $Logs "worker-error.log") -WindowStyle Hidden
}

Write-Host "Qwen embeddings: http://127.0.0.1:8088 (healthy)"
Write-Host "RAG API:         http://127.0.0.1:8018"
Write-Host "API docs:        http://127.0.0.1:8018/docs"
Write-Host "Worker:          running or starting"


