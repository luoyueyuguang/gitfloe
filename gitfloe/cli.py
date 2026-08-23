"""Command-line entry point: python -m gitfloe.cli --config repos.yaml."""
from __future__ import annotations

import argparse
import json
import os

from . import digest
from .config import load_config
from .core import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="gitfloe", description="Sync forks to upstream.")
    parser.add_argument("--config", default="repos.yaml", help="path to repos.yaml")
    parser.add_argument("--dry-run", action="store_true", help="report without merging/pushing")
    parser.add_argument("--digest-interval", action="store_true",
                        help="send an aggregate digest since the last one (no syncing)")
    parser.add_argument("--no-digest", action="store_true",
                        help="disable the per-run digest even if config enables it")
    args = parser.parse_args()

    token = os.getenv("GITFLOE_TOKEN") or os.getenv("GH_TOKEN")

    if args.digest_interval:
        cfg = load_config(args.config)
        if cfg.digest.on_interval:
            result = digest.send_interval_digest()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"digest_interval": "disabled (digest.on_interval=false)"}, indent=2, ensure_ascii=False))
        return

    cfg = load_config(args.config)
    results = run(cfg, token=token, dry_run=args.dry_run)
    print(json.dumps(results, indent=2, ensure_ascii=False))

    if cfg.digest.on_run and not args.no_digest and not args.dry_run:
        result = digest.send_run_digest(results)
        print(json.dumps({"run_digest": result}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
