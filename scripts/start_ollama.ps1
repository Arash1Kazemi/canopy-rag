# Starts the local model server from the standalone folder, with the models kept on E:.
# The settings apply to this one process only. Nothing is written to Windows settings.
# Leave this window open while the experiments run, and close it (Ctrl+C) when you are done.
param(
    [string]$OllamaDir = "E:\UNI\Semesterr 7\AI-Engineering\ollama",
    [string]$ModelsDir = "E:\UNI\Semesterr 7\AI-Engineering\ollama-models"
)
$env:OLLAMA_MODELS = $ModelsDir
# The address is this machine only. Port 11434 (Ollama's default) was reserved by Windows after a restart
# (range 11379-11478), so we use 11500. The runner reads the same port from baseline_runner/config.py.
$env:OLLAMA_HOST = "127.0.0.1:11500"
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
& (Join-Path $OllamaDir "ollama.exe") serve
