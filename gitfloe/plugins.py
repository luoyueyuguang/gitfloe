"""Pluggable attention-handler discovery.

A handler is any Python module that exposes:
    HANDLER = "name"                 # the plugin's unique name
    def handle(event: dict) -> dict: # returns {"handled": bool, "summary": str}

Handlers are found in two places:
  1. the built-in gitfloe/handlers/ directory, and
  2. any extra directories listed in the GITFLOE_HANDLER_PATH env var
     (colon-separated). Drop a .py file there and it becomes available without
     touching this package — that's the hook for other people to add their own
     logic (e.g. an AI handler that suggests a resolution).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Callable

Handler = Callable[[dict], dict]

_BUILTINS_DIR = Path(__file__).parent / "handlers"


def _load_module(path: Path):
    modname = "_gitfloe_handler_" + path.stem
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _collect(directory: Path, registry: dict[str, Handler]) -> None:
    if not directory.exists():
        return
    for p in sorted(directory.glob("*.py")):
        if p.stem.startswith("_"):
            continue
        try:
            mod = _load_module(p)
        except Exception:
            continue
        if mod is None:
            continue
        fn = getattr(mod, "handle", None)
        if not callable(fn):
            continue
        name = getattr(mod, "HANDLER", None) or p.stem
        registry[name] = fn


def extra_handler_dirs() -> list[Path]:
    """Parse GITFLOE_HANDLER_PATH (colon-separated) into Paths."""
    raw = os.getenv("GITFLOE_HANDLER_PATH", "")
    return [Path(p) for p in raw.split(":") if p.strip()]


def discover(handler_paths: list[Path] | None = None) -> dict[str, Handler]:
    """Return {handler_name: handle_fn}. External dirs override built-ins."""
    registry: dict[str, Handler] = {}
    _collect(_BUILTINS_DIR, registry)
    for d in (handler_paths if handler_paths is not None else extra_handler_dirs()):
        _collect(d, registry)
    return registry


def dispatch(
    handlers: dict[str, Handler],
    name: str | None,
    default: str,
    event: dict,
) -> dict:
    """Run the named handler (falling back to the default). Never raises."""
    chosen = (name or default) if (name or default) else default
    fn = handlers.get(chosen) or handlers.get(default)
    if fn is None:
        return {
            "handled": False,
            "summary": "no handler for '" + chosen + "' (default '" + default + "' unavailable)",
        }
    try:
        result = fn(event)
        return result or {"handled": False, "summary": "handler '" + chosen + "' returned nothing"}
    except Exception as exc:  # keep the run going
        return {"handled": False, "summary": "handler '" + chosen + "' failed: " + str(exc)}
