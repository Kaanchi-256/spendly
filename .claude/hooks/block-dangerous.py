#!/usr/bin/env python3
"""PreToolUse hook: block destructive operations that target protected files.

Registered in .claude/settings.json for the Bash, Write, Edit and MultiEdit
tools. Exit 2 + stderr message tells the harness to block the call.
"""
import json
import re
import sys

# Files / directories that must never be deleted, moved, truncated or
# overwritten by a tool call. Matched case-insensitively against a basename
# or a path fragment.
PROTECTED = [
    "important_textfile.txt",
    ".env",
    "migrations/",
]

# Destructive shell verbs (whole-word match, so "npm" / "chmod" don't trip).
DANGEROUS_RE = re.compile(
    r"(?:^|[^\w./-])(?:rm|unlink|shred|mv|truncate|dd)(?:[^\w./-]|$)"
    r"|>\s*[^|&>]",  # output redirection that would overwrite a file
)

try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

tool = data.get("tool_name", "")
tool_input = data.get("tool_input", {}) or {}


def block(target, reason):
    print(f"BLOCKED: {reason} — '{target}' is protected", file=sys.stderr)
    sys.exit(2)


def hits_protected(text):
    low = text.lower()
    for p in PROTECTED:
        if p.lower() in low:
            return p
    return None


if tool == "Bash":
    command = tool_input.get("command", "")
    if DANGEROUS_RE.search(command):
        p = hits_protected(command)
        if p:
            block(p, f"destructive command '{command.strip()}'")
elif tool in ("Write", "Edit", "MultiEdit"):
    # Write overwrites; Edit/MultiEdit mutate in place — both count.
    path = tool_input.get("file_path", "")
    p = hits_protected(path)
    if p:
        block(p, f"{tool} would modify {path}")

sys.exit(0)
