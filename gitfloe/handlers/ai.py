"""EXAMPLE third-party handler: ask an LLM to suggest how to resolve a conflict.

This is here to show the hook pattern — you can write your own handler the same
way and drop it into your handler path. It calls an OpenAI-compatible
chat/completions endpoint when configured, otherwise it degrades to a no-op.

Env vars:
    GITFLOE_AI_ENDPOINT   e.g. https://api.openai.com/v1/chat/completions
    GITFLOE_AI_KEY        bearer token
    GITFLOE_AI_MODEL      default: gpt-4o-mini
"""
from __future__ import annotations

import json
import os
import urllib.request

HANDLER = "ai"


def _prompt(event: dict) -> str:
    return (
        "You maintain a fork of an upstream repo with a merge conflict.\n"
        "fork: " + str(event.get("fork")) +
        "\nupstream: " + str(event.get("upstream")) +
        "\nbranch: " + str(event.get("branch")) +
        "\nkind: " + str(event.get("kind")) +
        "\nupstream commits:\n" + json.dumps(event.get("upstream_commits", []), indent=2) +
        "\nyour commits:\n" + json.dumps(event.get("local_commits", []), indent=2) +
        "\nSuggest one concrete resolution path (which side to take, or how to rebase)."
    )


def handle(event: dict) -> dict:
    endpoint = os.getenv("GITFLOE_AI_ENDPOINT", "").strip()
    if not endpoint:
        return {
            "handled": False,
            "summary": "[ai] not configured (GITFLOE_AI_ENDPOINT unset) for " + str(event.get("repo")),
        }

    key = os.getenv("GITFLOE_AI_KEY", "")
    model = os.getenv("GITFLOE_AI_MODEL", "gpt-4o-mini")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": _prompt(event)}],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + key} if key else {})},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    text = data["choices"][0]["message"]["content"]
    return {"handled": True, "summary": "[ai] " + text}
