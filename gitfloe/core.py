"""Sync orchestration via GitHub's merge-upstream API (the "Sync fork" button).

No git, no local clone: for each fork we call
    POST /repos/{owner}/{repo}/merge-upstream   {"branch": "<branch>"}
which is exactly what the GitHub web "Sync fork" button and `gh repo sync` do.

Response codes:
    200 = merged          204 = already up to date
    409 = conflict        (-> dispatched to a handler, default: email)
    403 / 404 = error     (-> dispatched to a handler)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import digest
from .config import Config, RepoConfig
from .plugins import Handler, discover, dispatch

API_BASE = os.getenv("GITFLOE_API_BASE", "https://api.github.com")


def _token() -> str:
    return os.getenv("GITFLOE_TOKEN") or os.getenv("GH_TOKEN") or ""


def _headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gitfloe",
        "Content-Type": "application/json",
        **({"Authorization": "Bearer " + token} if token else {}),
    }


def _request(method: str, url: str, token: str, body: bytes | None = None):
    req = urllib.request.Request(url, data=body, method=method, headers=_headers(token))
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"message": raw}
    except Exception as exc:
        return None, {"message": str(exc)}


def sync_repo(repo: RepoConfig, token: str, handlers: dict[str, Handler], dry_run: bool) -> dict:
    event = {"repo": repo.name, "fork": repo.fork, "upstream": repo.upstream, "branch": repo.branch}

    if dry_run:
        # Side-effect-free config check (read-only GET, no mutation).
        status, data = _request("GET", f"{API_BASE}/repos/{repo.fork}", token)
        if status == 200:
            event["kind"] = "preview"
            parent = (data.get("parent") or {}).get("full_name")
            if not data.get("fork"):
                event["summary"] = f"[dry-run] {repo.fork}: NOT a fork on GitHub (merge-upstream would fail)"
            elif parent and parent != repo.upstream:
                event["summary"] = f"[dry-run] {repo.fork}: config upstream {repo.upstream} != GitHub parent {parent}"
            else:
                event["summary"] = (f"[dry-run] {repo.fork}: would call "
                                    f"POST /repos/{repo.fork}/merge-upstream (branch={repo.branch})")
        else:
            event["kind"] = "error"
            event["summary"] = f"[dry-run] {repo.fork}: GET failed HTTP {status}: {data.get('message', '')}"
        return event

    status, data = _request("POST", f"{API_BASE}/repos/{repo.fork}/merge-upstream", token,
                            json.dumps({"branch": repo.branch}).encode())
    event["api_status"] = status
    if status == 200:
        event["kind"] = "synced"
        event["summary"] = (f"synced {repo.fork} ({data.get('merge_type', 'merge')} on "
                            f"{data.get('base_branch', repo.branch)})")
    elif status == 204:
        event["kind"] = "up_to_date"
        event["summary"] = f"{repo.fork} already up to date with upstream"
    elif status == 409:
        event["kind"] = "conflict"
        event["error"] = data.get("message", "merge conflict")
    elif status == 403:
        event["kind"] = "error"
        event["error"] = data.get("message", "permission denied (does GITFLOE_TOKEN have Contents:write on the fork?)")
    elif status == 404:
        event["kind"] = "error"
        event["error"] = data.get("message", "not found (is it a real fork? is the upstream correct?)")
    else:
        event["kind"] = "error"
        event["error"] = f"HTTP {status}: {data.get('message', '')}" if isinstance(data, dict) else f"HTTP {status}"

    if event["kind"] in ("conflict", "error"):
        out = dispatch(handlers, repo.handler, "email", event)
        event["handler"] = out["summary"]
        event["handled"] = out["handled"]
    return event


def run(cfg: Config, token: str | None = None, dry_run: bool = False) -> list[dict]:
    handlers = discover()
    token = token or _token()
    results: list[dict] = []
    for repo in cfg.repos:
        try:
            event = sync_repo(repo, token, handlers, dry_run)
        except Exception as exc:
            event = {"repo": repo.name, "fork": repo.fork, "upstream": repo.upstream, "kind": "error", "error": str(exc)}
        results.append(event)
    if not dry_run:
        digest.record_events(results)
    return results
