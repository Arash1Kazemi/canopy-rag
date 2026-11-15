"""Memory readings for the speed and memory metrics (M25). A reading may be missing, and none may stop a run."""
import os
import subprocess


def _run(command, timeout=20):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def gpu_used_mb():
    """GPU memory in use, in MB, from nvidia-smi. It includes what Windows itself uses."""
    first_line = _run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).splitlines()[:1]
    return int(first_line[0].strip()) if first_line and first_line[0].strip().isdigit() else None


def ollama_ram_mb():
    """System memory used by the Ollama processes, in MB."""
    text = _run(["powershell", "-NoProfile", "-Command",
                 "(Get-Process -Name 'ollama*' -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1MB"])
    try:
        return int(float(text))
    except ValueError:
        return None


def ollama_ps():
    """The output of `ollama ps`: which share of each loaded model is on the GPU and which on the CPU."""
    return _run([os.environ.get("OLLAMA_EXE", "ollama"), "ps"])


def snapshot():
    return {"gpu_mb": gpu_used_mb(), "ram_mb": ollama_ram_mb()}
