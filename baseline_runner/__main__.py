"""Command line.  python -m baseline_runner <command> [options]   (run it from )

  list    show the shortlisted models and whether they are downloaded
  check   is the local server running, and which shortlisted models are ready
  pull    download shortlisted models of a tier (this is the only command that downloads)
  e1 e2 e3 e4 e5 e6   the experiments of prompt_test_plan.md
  regrade --run-id <run>   grade the saved answers of an e2 or e3 run again (no model needed)

Add --fake to run any experiment with no model and no network (a dry run of the pipeline).
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from . import experiments as ex
from . import system_info
from .config import BASELINE_CHUNKS, BASELINE_K, JUDGE_PROBE, RESULTS
from .corpus import read_csv
from .fakes import FakeClient
from .ollama_api import OllamaClient, OllamaError

COMMANDS = ("list", "check", "pull", "e1", "e2", "e3", "e4", "e5", "e6", "regrade")


def shortlisted(registry, task, max_tier=3):
    return [mid for mid, row in registry.items()
            if row["task"] == task and row["status"] == "shortlisted" and int(row["tier"]) <= max_tier]


def pick(args, registry, task):
    if args.models:
        ids = [m.strip() for m in args.models.split(",")]
        unknown = [m for m in ids if m not in registry]
        if unknown:
            raise SystemExit(f"unknown model ids: {unknown}. Known: {sorted(registry)}")
        return ids
    return shortlisted(registry, task)


def parse(argv):
    parser = argparse.ArgumentParser(prog="baseline_runner", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--fake", action="store_true", help="no model, no network: a dry run")
    parser.add_argument("--out", type=Path, help="results folder (default: results/<run id>)")
    parser.add_argument("--run-id", help="name of the run (default: the date and time)")
    parser.add_argument("--models", help="comma separated model ids (default: the shortlisted models of the right task)")
    parser.add_argument("--embedding", help="embedding model id used for retrieval in e3 and e6")
    parser.add_argument("--chunks", default=BASELINE_CHUNKS, help="chunk setting for e3 and e6")
    parser.add_argument("--k", type=int, default=BASELINE_K, help="chunks per question for e3")
    parser.add_argument("--tier", type=int, default=1, help="pull: download tiers up to this number")
    parser.add_argument("--images", nargs="*", type=Path, help="e4: page images to read")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    registry = ex.load_registry()
    client = FakeClient() if args.fake else OllamaClient()

    if args.command == "list":
        pulled = {} if args.fake else _safe_models(client)
        for mid, row in registry.items():
            state = "ready" if row["runtime_tag"] in pulled else ("-" if row["status"] == "shortlisted" else "")
            print(f"{row['task']:<9}{mid:<24}{row['runtime_tag']:<26}tier {row['tier']}  {row['status']:<12}{row['download_gb']:>6} GB  {state}")
        return 0

    if args.command == "check":
        try:
            print("server version:", client.version())
        except OllamaError as error:
            print("server not reachable:", error)
            return 1
        pulled = client.models()
        for mid, row in registry.items():
            if row["status"] == "shortlisted":
                print(f"{'ready  ' if row['runtime_tag'] in pulled else 'missing'} {mid} ({row['runtime_tag']}, tier {row['tier']})")
        print("GPU memory in use (MB):", system_info.gpu_used_mb())
        return 0

    if args.command == "pull":
        exe = os.environ.get("OLLAMA_EXE", "ollama")
        for mid, row in registry.items():
            if row["status"] == "shortlisted" and int(row["tier"]) <= args.tier:
                print(f"pulling {row['runtime_tag']} ({row['download_gb']} GB)")
                if subprocess.run([exe, "pull", row["runtime_tag"]]).returncode != 0:
                    return 1
        return 0

    if args.command == "regrade":
        if not args.run_id:
            raise SystemExit("regrade needs --run-id <an e2 or e3 run>")
        run_dir = args.out or RESULTS / args.run_id
        ctx = ex.make_context(FakeClient(), run_dir, sampler=lambda: {}, ps=lambda: "")
        for name in ("e2", "e3"):
            if (run_dir / f"{name}_rows.csv").exists():
                for row in ex.regrade(ctx, run_dir, name):
                    print(f"{name} {row['llm']}: M01 {row['M01']:.3f}  M02 {row['M02']:.3f}")
        return 0

    run_id = args.run_id or ("fake-" if args.fake else "") + time.strftime("%Y%m%d-%H%M%S")
    quiet = {"sampler": lambda: {}, "ps": lambda: ""} if args.fake else {}
    ctx = ex.make_context(client, args.out or RESULTS / run_id, **quiet)
    embedding = args.embedding or ("nomic-embed-text" if args.fake else None)

    if args.command == "e1":
        ex.write_meta(ctx, command="e1")
        ex.run_e1(ctx, pick(args, registry, "embedding"))
    elif args.command == "e2":
        ex.write_meta(ctx, command="e2")
        ex.run_e2(ctx, pick(args, registry, "llm"))
    elif args.command in ("e3", "e6"):
        if not embedding:
            raise SystemExit("e3 and e6 need --embedding <model id>, chosen from the e1 results")
        ex.write_meta(ctx, command=args.command, embedding=embedding, chunks=args.chunks, k=args.k)
        runner = ex.run_e3 if args.command == "e3" else ex.run_e6
        kwargs = {"k": args.k} if args.command == "e3" else {}
        runner(ctx, pick(args, registry, "llm"), embedding, chunk_name=args.chunks, **kwargs)
    elif args.command == "e4":
        images = args.images or [p for p in (RESULTS / "inputs").glob("d19_*.png")]
        if not images:
            raise SystemExit("e4 needs page images: run scripts/render_d19.ps1 first, or pass --images")
        ex.write_meta(ctx, command="e4", images=[str(p) for p in images])
        ex.run_e4(ctx, pick(args, registry, "lvm"), images)
    elif args.command == "e5":
        ex.write_meta(ctx, command="e5")
        ex.run_e5(ctx, pick(args, registry, "llm"), read_csv(JUDGE_PROBE))
    print("results in", ctx.out_dir)
    return 0


def _safe_models(client):
    try:
        return client.models()
    except OllamaError:
        return {}


if __name__ == "__main__":
    sys.exit(main())
