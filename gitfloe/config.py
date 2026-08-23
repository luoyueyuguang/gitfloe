"""Config loading from repos.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RepoConfig:
    name: str
    fork: str
    upstream: str
    branch: str = "main"
    strategy: str = "auto"       # auto | pr
    handler: str | None = None   # plugin name; None -> use default


@dataclass
class DigestConfig:
    on_run: bool = False       # email a digest after each sync run
    on_interval: bool = False  # email an aggregate digest on a schedule (digest.yml)


@dataclass
class Config:
    branch: str = "main"
    strategy: str = "auto"
    handler: str = "email"       # default plugin when a repo doesn't override
    digest: DigestConfig = field(default_factory=DigestConfig)
    repos: list[RepoConfig] = field(default_factory=list)


def load_config(path: str | Path) -> Config:
    """Load and normalize repos.yaml into a Config."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = raw.get("default", {}) or {}

    cfg = Config(
        branch=defaults.get("branch", "main"),
        strategy=defaults.get("strategy", "auto"),
        handler=defaults.get("handler", "email"),
    )

    d = raw.get("digest", {}) or {}
    cfg.digest = DigestConfig(
        on_run=bool(d.get("on_run", False)),
        on_interval=bool(d.get("on_interval", False)),
    )

    cfg.repos = []
    for item in raw.get("repos", []) or []:
        cfg.repos.append(
            RepoConfig(
                name=str(item["name"]),
                fork=str(item["fork"]),
                upstream=str(item["upstream"]),
                branch=str(item.get("branch", cfg.branch)),
                strategy=str(item.get("strategy", cfg.strategy)),
                handler=item.get("handler") or cfg.handler,
            )
        )
    return cfg
