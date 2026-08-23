"""Digest: turn sync events into an aggregate email summary.

Two modes:
  * run digest      — emailed right after each sync run (config: digest.on_run)
  * interval digest — emailed on a schedule, aggregating events since the last one
                      (config: digest.on_interval; run with --digest-interval)

Events are persisted to state/events.jsonl so the interval digest can aggregate
across workflow runs; that file and state/ are committed back by the workflows.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import smtp

EVENTS_FILE = Path(os.getenv("GITFLOE_EVENTS", "./state/events.jsonl"))
LAST_DIGEST_FILE = Path(os.getenv("GITFLOE_LAST_DIGEST", "./state/last_digest.json"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_events(events: list[dict]) -> None:
    """Append each event (with a timestamp) to the persistent event log."""
    if not events:
        return
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = _now()
    with open(EVENTS_FILE, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps({"ts": ts, **e}, ensure_ascii=False) + "\n")


def load_events(since: str | None = None) -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    out = []
    for line in EVENTS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if since and str(e.get("ts", "")) < since:
            continue
        out.append(e)
    return out


def last_digest_ts() -> str | None:
    if not LAST_DIGEST_FILE.exists():
        return None
    try:
        return json.loads(LAST_DIGEST_FILE.read_text(encoding="utf-8")).get("ts")
    except Exception:
        return None


def mark_digest() -> None:
    LAST_DIGEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_DIGEST_FILE.write_text(json.dumps({"ts": _now()}, ensure_ascii=False), encoding="utf-8")


def aggregate(events: list[dict]) -> dict:
    counts: Counter = Counter(e.get("kind") for e in events)
    repos: dict = {}
    for e in events:
        name = e.get("repo", "?")
        info = repos.setdefault(name, {"fork": e.get("fork"), "upstream": e.get("upstream"), "kinds": Counter()})
        info["kinds"][e.get("kind")] += 1
        if e.get("handler"):
            info["last_handler"] = e["handler"]
        if e.get("error"):
            info["last_error"] = e["error"]
        if e.get("summary"):
            info["last_summary"] = e["summary"]
    return {"total": len(events), "counts": dict(counts), "repos": repos}


def render(agg: dict, scope: str) -> str:
    lines = ["# gitfloe digest", "scope: " + scope, ""]
    counts = agg["counts"]
    lines.append("outcomes: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) if counts else "none"))
    lines.append("repos touched: " + str(len(agg["repos"])))
    lines.append("")
    for name, info in sorted(agg["repos"].items()):
        kinds = ", ".join(f"{k}={v}" for k, v in info["kinds"].items())
        lines.append("- " + name + " (" + str(info.get("fork")) + " <- " + str(info.get("upstream")) + ") k=" + kinds)
        if info.get("last_summary"):
            lines.append("    " + info["last_summary"])
        if info.get("last_error"):
            lines.append("    error: " + info["last_error"])
        if info.get("last_handler"):
            lines.append("    handler: " + info["last_handler"])
    return "\n".join(lines)


def send_run_digest(events: list[dict]) -> dict:
    """Digest of one run. No-op (returns empty) if nothing to report or no SMTP."""
    if not events:
        return {"sent": False, "reason": "no events"}
    agg = aggregate(events)
    body = render(agg, "this run")
    ok = smtp.send("[gitfloe] sync summary", body)
    return {"sent": ok, "reason": "" if ok else "SMTP not configured", "outcomes": agg["counts"]}


def send_interval_digest() -> dict:
    """Digest since the last one. Records the new watermark only if it sent."""
    since = last_digest_ts()
    events = load_events(since)
    if not events:
        return {"sent": False, "reason": "no events since last digest"}
    agg = aggregate(events)
    body = render(agg, "since " + (since or "beginning"))
    ok = smtp.send("[gitfloe] periodic summary", body)
    if ok:
        mark_digest()
    return {"sent": ok, "reason": "" if ok else "SMTP not configured", "outcomes": agg["counts"]}
