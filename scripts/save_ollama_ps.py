"""Save `ollama ps` and `nvidia-smi` output with a UTC time stamp. Only local programs are run; nothing goes to the network.

Run from UNI-Project/ (PowerShell):

    & $py scripts\\save_ollama_ps.py --out results\\<run id>                 one snapshot
    & $py scripts\\save_ollama_ps.py --out results\\<run id> --every 30 --count 20   20 snapshots, 30 s apart

Each snapshot is one file, ollama_ps_<UTC time>.txt, in the given folder. A missing program is written into the
file as a note and does not stop the run. The program for `ollama` is taken from the OLLAMA_EXE variable, as in
baseline_runner/system_info.py, unless --ollama is given.
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

NVIDIA_SMI = ["nvidia-smi"]


def run_command(command, timeout=30):
    """Run one local program. Returns (exit code, text of its output). The exit code is None when it could not run."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None, f"not available: '{command[0]}' was not found on this computer"
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"not available: '{command[0]}' could not run ({error})"
    return done.returncode, (done.stdout + done.stderr).strip()


def stamp_of(moment):
    return moment.strftime("%Y%m%dT%H%M%SZ")


def unique_path(folder, stamp):
    """ollama_ps_<stamp>.txt, or with _2, _3 ... added when two snapshots fall in the same second."""
    path = folder / f"ollama_ps_{stamp}.txt"
    number = 2
    while path.exists():
        path = folder / f"ollama_ps_{stamp}_{number}.txt"
        number += 1
    return path


def take_snapshot(out_dir, ollama_exe, runner=run_command, now=None):
    """Write one snapshot file and return its path. Both commands are run even if the first one fails."""
    moment = now() if now else datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = unique_path(out_dir, stamp_of(moment))
    sections = [("ollama ps", [ollama_exe, "ps"]), ("nvidia-smi", NVIDIA_SMI)]
    lines = [f"UTC time: {moment.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for label, command in sections:
        code, text = runner(command)
        lines += [f"== {label} ==", f"exit code: {code if code is not None else 'none'}", text or "(no output)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="results folder, for example results\\<run id>")
    parser.add_argument("--every", type=float, default=0, help="seconds between snapshots (needs --count above 1)")
    parser.add_argument("--count", type=int, default=1, help="how many snapshots to take (default 1)")
    parser.add_argument("--ollama", default=os.environ.get("OLLAMA_EXE", "ollama"), help="the ollama program")
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.count > 1 and args.every <= 0:
        parser.error("--every must be more than 0 seconds when --count is above 1")
    return args


def main(argv=None, runner=run_command, sleep=time.sleep, now=None):
    args = parse(argv)
    for number in range(args.count):
        if number:
            sleep(args.every)
        path = take_snapshot(args.out, args.ollama, runner=runner, now=now)
        print("saved", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
