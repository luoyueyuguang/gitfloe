# gitfloe

<p align="center"><img src="assets/logo-lockup.svg" alt="gitfloe" width="420"/></p>

<p align="center">
  <img src="https://img.shields.io/github/license/luoyueyuguang/gitfloe" alt="License: MIT">
  <img src="https://img.shields.io/badge/python-3.12-3776AB" alt="Python 3.12">
  <img src="https://img.shields.io/github/stars/luoyueyuguang/gitfloe" alt="GitHub stars">
  <img src="https://img.shields.io/badge/sync-merge--upstream-38bdf8" alt="merge-upstream sync">
  <img src="https://img.shields.io/github/actions/workflow/status/luoyueyuguang/gitfloe/ci.yml?branch=main" alt="CI passing">
</p>

Keep your **forks** in sync with their upstreams by calling GitHub's `merge-upstream` API — the
exact same thing the web "Sync fork" button and `gh repo sync` do. **No git, no cloning.** When a
fork has a **conflict**, it hands off to a **pluggable handler** (default: email). After each run —
and periodically — it also emails an **overall digest** of what happened.

## What it does

One repo ("the manager") holds a list of your forks and, on a schedule, for each one:

1. calls `POST /repos/{owner}/{repo}/merge-upstream` with `{"branch": "<branch>"}`,
2. reads the result:
   - **200** → merged (synced),
   - **204** → already up to date,
   - **409** → **conflict** → dispatch a handler (default: email),
   - **403 / 404 / other** → error → dispatch a handler,
3. records each result to `state/events.jsonl` and emails a **digest**.

It only ever writes to *your* forks (via the API), never to upstream.

## Layout

    repos.yaml                       # forks + strategies + handlers + digest toggles
    gitfloe/
      cli.py                         # python -m gitfloe.cli
      core.py                        # calls merge-upstream; classifies result; dispatches
      config.py                      # load repos.yaml
      plugins.py                     # handler discovery + dispatch
      smtp.py                        # shared SMTP sender (env-driven)
      digest.py                      # run + interval digest
      handlers/
        email.py                     # default: email on conflict/error
        ai.py                        # example LLM handler (shows the hook)
    .github/workflows/
      sync.yml                       # scheduled sync + per-run digest + state commit
      digest.yml                     # weekly aggregate digest
    state/                           # committed back so history persists across runs
    .env.example                     # local secrets template (never commit .env)

## Adding your forks

Copy the template `examples/repos.example.yaml` to `repos.yaml`, then edit it:

    default:
      branch: main
      handler: email
    digest:
      on_run: true              # email a summary after every sync run
      on_interval: true         # + weekly digest via digest.yml
    repos:
      - name: example-fork
        fork: you/example-fork
        upstream: someorg/example
        branch: main

> `upstream` is for reference/labels (the API derives it from the fork's GitHub parent); `branch`
> is the branch `merge-upstream` merges into.

## The handler hook

A handler is a Python module exposing `HANDLER` and `handle(event)`:

    # handlers/mine.py
    HANDLER = "my-name"
    def handle(event: dict) -> dict:
        # repo, fork, upstream, branch, kind, api_status, error, summary
        return {"handled": True, "summary": "did something"}

The event `kind` is `synced` / `up_to_date` / `conflict` / `error` (plus `preview` during dry-run).
Return `{"handled": False}` to leave it for another handler / log only. External handlers: drop
`.py` in a folder and point the run at it via `GITFLOE_HANDLER_PATH` (colon-separated); external
ones override by name.

## Running locally

    pip install -r requirements.txt
    python -m gitfloe.cli --config repos.yaml --dry-run      # config/validation check (read-only)
    python -m gitfloe.cli --config repos.yaml                # actually sync (needs GITFLOE_TOKEN)
    python -m gitfloe.cli --config repos.yaml --digest-interval  # send periodic digest only

You can also trigger a single fork manually with the official CLI:

    gh repo sync luoyueyuguang/vllm --branch main

## Where the secrets live (the key point)

**No secret is ever committed.** Credentials come from the environment — GitHub Actions **Secrets**
in CI, a local `.env` for development.

| Secret | Used by | Purpose |
| --- | --- | --- |
| `GITFLOE_TOKEN` | core | PAT/fine-grained token on **your forks** with `Contents: write` (the API needs it to push the merge). |
| `GITFLOE_SMTP_HOST/PORT/USER/PASS` | smtp | SMTP for the email handler + digest. |
| `GITFLOE_MAIL_TO` | smtp | Where attention + digest emails go. |
| `GITFLOE_AI_ENDPOINT` | ai handler | LLM endpoint (OpenAI-compatible). |
| `GITFLOE_AI_KEY` | ai handler | LLM bearer token. |
| `GITFLOE_AI_MODEL` | ai handler | Model id (default `gpt-4o-mini`). |

**LLM token — same rule as the sync token:** put `GITFLOE_AI_KEY` (+ END/MODEL) in Secrets, injected
by the workflow's `env:`. Local runs read them from `.env`. If unset, the `ai` handler degrades to a no-op.

> Tip: for Gmail use an **App Password** + `smtp.gmail.com:587`.

## State persistence

`state/` is **tracked** so the digest can aggregate across workflow runs; both workflows commit it
back. Peek at the event log: `tail -f state/events.jsonl`.
