"""Default handler: email the user when a fork needs attention (e.g. conflict).

Uses the shared SMTP sender (gitfloe.smtp), which reads credentials from env
vars (GitHub Actions secrets, or a local .env). Nothing is read from config.
"""
from __future__ import annotations

from gitfloe import smtp

HANDLER = "email"


def _subject(event: dict) -> str:
    kind = event.get("kind", "event")
    return "[gitfloe] " + str(kind) + ": " + str(event.get("repo", "repo")) + " needs attention"


def _render(event: dict) -> str:
    lines = [
        "repo:      " + str(event.get("fork", "?")),
        "upstream:  " + str(event.get("upstream", "?")),
        "branch:    " + str(event.get("branch", "?")),
        "kind:      " + str(event.get("kind", "?")),
        "local:     " + str(event.get("local_head", "?"))[:12],
        "upstream:  " + str(event.get("upstream_head", "?"))[:12],
    ]
    if event.get("error"):
        lines.append("error:     " + str(event["error"]))
    for label in ("behind", "ahead"):
        if event.get(label) is not None:
            lines.append(label + ": " + str(event[label]))
    for side, key in (("upstream commits", "upstream_commits"), ("your commits", "local_commits")):
        commits = event.get(key)
        if commits:
            lines.append(side + ":")
            for c in commits[:10]:
                lines.append("  - " + str(c))
    return "\n".join(lines)


def handle(event: dict) -> dict:
    if not smtp.configured():
        return {
            "handled": False,
            "summary": "[email] skipped: SMTP not configured for " + str(event.get("repo")),
        }
    ok = smtp.send(_subject(event), _render(event))
    return {
        "handled": ok,
        "summary": ("[email] sent notice for " + str(event.get("repo"))) if ok
                   else ("[email] send failed for " + str(event.get("repo"))),
    }
