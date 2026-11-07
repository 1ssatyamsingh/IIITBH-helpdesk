@echo off
setlocal
set "ROOT=%~dp0"
start "IIITBH RAG Local Services" powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%backend\scripts\start_local_stack.ps1"
start "IIITBH RAG Frontend" cmd /k "cd /d "%ROOT%frontend" && npm.cmd run dev -- --host 0.0.0.0 --port 5174 --strictPort"
echo.
echo Starting local Qwen embeddings, API, ingestion worker and frontend.
echo Frontend: http://127.0.0.1:5174
echo API docs: http://127.0.0.1:8018/docs
endlocal


