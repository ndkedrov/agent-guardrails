#!/usr/bin/env python3
"""SessionStart hook for Claude Code and Codex: injects the guardrails digest into the session."""
import json
import os
import sys

LIMIT = 2900  # Codex hooks cap injected context (3000 chars in common configs)


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    if os.environ.get('AGENT_GUARDRAILS') == 'off':
        return 0
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'DIGEST.md')
    try:
        with open(path, encoding='utf-8') as handle:
            digest = handle.read().strip()[:LIMIT]
    except OSError:
        return 0
    sys.stdout.write(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': digest}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
