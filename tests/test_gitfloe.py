"""Bootstrap tests for gitfloe (offline, no network)."""
import pytest


def test_config_load(tmp_path):
    from gitfloe.config import load_config
    p = tmp_path / "repos.yaml"
    p.write_text(
        "default:\n  branch: main\n  handler: email\n"
        "repos:\n  - name: a\n    fork: x/a\n    upstream: y/a\n"
    )
    cfg = load_config(p)
    assert cfg.repos[0].name == "a"
    assert cfg.repos[0].upstream == "y/a"


def test_plugins_discover():
    from gitfloe.plugins import discover
    h = discover()
    assert "email" in h and "ai" in h


def test_digest_aggregate_render():
    from gitfloe.digest import aggregate, render
    agg = aggregate([{"repo": "a", "fork": "x/a", "upstream": "y/a", "kind": "synced"}])
    assert agg["repos"]["a"]["kinds"]["synced"] == 1
    text = render(agg, "test")
    assert "gitfloe digest" in text


def test_core_run_callable():
    import gitfloe.core as core
    assert callable(core.run)
