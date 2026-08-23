# AGENTS.md

## What this is

`gitfloe` keeps your GitHub **forks** in sync with their upstreams by calling GitHub's
`merge-upstream` API — the exact thing the web "Sync fork" button and `gh repo sync` do.
**No git cloning.** When a fork conflicts it hands off to a **pluggable handler**
(default: email). Optionally it emails a **digest** of what happened.

## Architecture / key files

    assets/                       # logo (logo.svg, logo-light.svg, logo-lockup.svg, favicon.ico)
    examples/repos.example.yaml   # config template (copy to repos.yaml)
    gitfloe/
      cli.py                      # entry point: python -m gitfloe.cli
      core.py                     # calls merge-upstream, classifies result, dispatches handlers
      config.py                   # load repos.yaml
      plugins.py                  # handler discovery + dispatch
      smtp.py                     # shared SMTP sender (env-driven)
      digest.py                   # run + interval digest
      handlers/email.py           # default: email on conflict/error
      handlers/ai.py              # example LLM handler (shows the hook)
    tests/                        # pytest tests
    .github/workflows/sync.yml    # scheduled sync + per-run digest + state commit
    .github/workflows/digest.yml  # periodic aggregate digest
    .github/workflows/ci.yml      # CI + pytest
    state/                        # committed back so history persists across runs
    examples/.env.example            # local secrets template (never commit .env)

## Run

    pip install -r requirements.txt
    python -m gitfloe.cli --config repos.yaml --dry-run        # read-only config/validation
    python -m gitfloe.cli --config repos.yaml                  # real sync (needs GITFLOE_TOKEN)
    python -m gitfloe.cli --config repos.yaml --digest-interval  # periodic digest only

Manual single-fork sync: `gh repo sync <fork> --branch main`.

## Config (repos.yaml)

    default:
      branch: main
      strategy: auto        # info only; merge-upstream always merges
      handler: email
    digest:
      on_run: false         # email a summary after each run (requires SMTP)
      on_interval: false    # periodic digest via digest.yml
    repos:
      - name: example-fork
        fork: you/example-fork
        upstream: someorg/example
        branch: main

> `upstream` is reference/labels only (the API uses the fork's GitHub parent).

## Handler hook (extensibility)

A handler is a Python module exposing `HANDLER` + `handle(event)` returning
`{"handled": bool, "summary": str}`. Handlers are never called on `--dry-run` (side-effect free).

    # handlers/mine.py
    HANDLER = "my-name"
    def handle(event: dict) -> dict:
        # repo, fork, upstream, branch, kind, api_status, error, summary
        return {"handled": True, "summary": "did something"}

Event `kind`: `synced` | `up_to_date` | `conflict` | `error` (`preview` on dry-run).
External handlers: put `.py` in a folder, point `GITFLOE_HANDLER_PATH` (colon-separated)
at it; external override built-ins by name.

## merge-upstream result mapping

    200 -> synced      204 -> up_to_date
    409 -> conflict (-> handler)    403/404/other -> error (-> handler)

## Merging upstream changes (if you keep a private fork)

If you maintain a private **fork** of this repo with your own `repos.yaml`, be careful when
merging upstream: upstream no longer carries `repos.yaml` (it lives in `examples/repos.example.yaml`),
so a plain `git merge upstream/main` can treat your private `repos.yaml` as "deleted upstream" and
**drop it**. Before committing such a merge, restore it from the previous commit:

    git status                            # watch for repos.yaml missing
    git checkout <previous-commit> -- repos.yaml
    git add repos.yaml && git commit


## Secrets (env only; NEVER commit)

| `GITFLOE_TOKEN` | core | PAT on your forks with `Contents: write` (add `Workflows` if the upstream changes touch `.github/workflows/*`). |
| `GITFLOE_SMTP_HOST/PORT/USER/PASS` | smtp | SMTP for email handler + digest. |
| `GITFLOE_MAIL_TO` | smtp | Recipient for attention + digest emails. |
| `GITFLOE_AI_ENDPOINT/KEY/MODEL` | ai | LLM handler (unset -> no-op). |

Add `GITFLOE_TOKEN` (+ SMTP/AI if used) as GitHub Actions **Secrets**; locally use `.env`
(git-ignored). `GITFLOE_TOKEN` can be a fine-grained PAT — it must be scoped to the exact
forks, with `Contents: read and write` (and `Workflows: read and write` if needed).

## Conventions

- Python 3.12, stdlib only for the core (`urllib`, `json`, `os`, `yaml`) — no heavy deps.
- Type hints + `from __future__ import annotations`. No `enum`/namespaces in edits.
- Handlers must use **absolute** imports (`from gitfloe import smtp`) because they are
  loaded as standalone modules by `plugins.py`.
- Don't commit `.env`, `workspace/`, `__pycache__/`; `state/` IS tracked (digest history).
- Keep `--dry-run` side-effect free (no handler calls, no merge, no push).
- Notifications are **off by default** (`digest.on_run/on_interval: false`).
