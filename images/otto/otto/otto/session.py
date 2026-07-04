"""Persistent sessions: one JSONL file per session under ~/.otto.

On Zone the home directory is a persistent volume, so sessions survive
notebook restarts and image upgrades. Each line is one chat message dict,
appended as the conversation happens; compaction rewrites the file.
"""

import json
import os
import pathlib
import time


def sessions_dir():
    root = os.environ.get("OTTO_HOME", "~/.otto")
    path = pathlib.Path(root).expanduser() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_for(session_id):
    return sessions_dir() / (session_id + ".jsonl")


def new_id():
    base = time.strftime("%Y%m%d-%H%M%S")
    session_id, n = base, 1
    while path_for(session_id).exists():
        session_id = "%s-%d" % (base, n)
        n += 1
    return session_id


def append(session_id, message):
    with open(path_for(session_id), "a") as f:
        f.write(json.dumps(message) + "\n")


def load(session_id):
    target = path_for(session_id)
    if not target.exists():
        raise FileNotFoundError(
            "no session %s (list sessions with `otto --sessions`)" % session_id
        )
    with open(target) as f:
        return [json.loads(line) for line in f if line.strip()]


def rewrite(session_id, messages):
    with open(path_for(session_id), "w") as f:
        for message in messages:
            f.write(json.dumps(message) + "\n")


def latest():
    files = sorted(sessions_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1].stem if files else None


def listing():
    """Return (session_id, message_count, first_user_prompt) rows, newest first."""
    rows = []
    for f in sorted(sessions_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        messages = load(f.stem)
        first = next(
            (m.get("content") or "" for m in messages if m.get("role") == "user"), ""
        )
        rows.append((f.stem, len(messages), " ".join(first.split())[:60]))
    return rows
