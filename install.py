#!/usr/bin/env python3
"""Install, update or remove the agent-guardrails skill and hooks for Claude Code and Codex.

  python3 install.py                 # both agents that exist on this machine, skill + hooks
  python3 install.py --claude        # only Claude Code
  python3 install.py --codex         # only Codex
  python3 install.py --no-hooks      # skill only, no hooks
  python3 install.py --uninstall     # remove the skill and only this project's hook entries
  python3 install.py --dry-run       # show what would change

Only entries whose command points at agent-guardrails/hooks/ are ever added or removed; other hooks are kept.
Each modified settings file is backed up next to itself first.
"""
import argparse
import json
import os
import shutil
import sys
import time

NAME = 'agent-guardrails'
SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills', NAME)
MARK = NAME + '/hooks/'
START_MATCHER = 'startup|resume|clear|compact'


def hook_entries(skill_dir, agent):
    python = sys.executable or 'python3'
    start = {'type': 'command', 'command': '"%s" "%s"' % (python, os.path.join(skill_dir, 'hooks', 'session_start.py')), 'timeout': 10}
    guard = {'type': 'command', 'command': '"%s" "%s"' % (python, os.path.join(skill_dir, 'hooks', 'guard.py')), 'timeout': 10}
    if agent == 'codex':
        start['additionalContextLimit'] = 3000
        return {'SessionStart': {'matcher': START_MATCHER, 'hooks': [start]}, 'PreToolUse': {'matcher': '*', 'hooks': [guard]}}
    return {'SessionStart': {'matcher': START_MATCHER, 'hooks': [start]}, 'PreToolUse': {'matcher': 'Bash|Read', 'hooks': [guard]}}


def strip_ours(hooks):
    for event in list(hooks):
        groups = []
        for group in hooks[event]:
            kept = [h for h in group.get('hooks', []) if MARK not in str(h.get('command', ''))]
            if kept:
                groups.append(dict(group, hooks=kept))
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    return hooks


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    return json.loads(text) if text.strip() else {}


def save(path, data, dry):
    if dry:
        print('  would write', path)
        return
    if os.path.exists(path):
        backup = '%s.%s-%s.bak' % (path, NAME, time.strftime('%Y%m%d-%H%M%S'))
        shutil.copy2(path, backup)
        print('  backup', backup)
    temporary = path + '.tmp-' + NAME
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    with open(temporary, encoding='utf-8') as handle:
        json.load(handle)
    os.replace(temporary, path)
    print('  wrote', path)


def install_skill(target, dry):
    if os.path.exists(target) and not os.path.exists(os.path.join(target, '.' + NAME)):
        sys.exit('refusing to overwrite %s: it was not installed by %s' % (target, NAME))
    if dry:
        print('  would copy skill to', target)
        return
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    open(os.path.join(target, '.' + NAME), 'w').close()
    print('  skill', target)


def remove_skill(target, dry):
    if os.path.exists(os.path.join(target, '.' + NAME)):
        print('  would remove' if dry else '  removed', target)
        if not dry:
            shutil.rmtree(target)


def configure(agent, home, args):
    base = os.path.join(home, '.claude' if agent == 'claude' else '.codex')
    skill_dir = os.path.join(base, 'skills', NAME)
    settings = os.path.join(base, 'settings.json' if agent == 'claude' else 'hooks.json')
    print('%s (%s)' % ('Claude Code' if agent == 'claude' else 'Codex', base))
    data = load(settings)
    hooks = strip_ours(data.get('hooks', {}))
    if args.uninstall:
        remove_skill(skill_dir, args.dry_run)
    else:
        os.makedirs(os.path.dirname(skill_dir), exist_ok=True)
        install_skill(skill_dir, args.dry_run)
        if not args.no_hooks:
            for event, group in hook_entries(skill_dir, agent).items():
                hooks.setdefault(event, []).append(group)
    if hooks:
        data['hooks'] = hooks
    else:
        data.pop('hooks', None)
    if os.path.exists(settings) or data:
        save(settings, data, args.dry_run)
    if agent == 'codex' and not args.uninstall and not args.no_hooks:
        print('  note: Codex runs new or changed hooks only after you review and trust them in Codex.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--claude', action='store_true')
    parser.add_argument('--codex', action='store_true')
    parser.add_argument('--no-hooks', action='store_true')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--home', default=os.path.expanduser('~'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    agents = [a for a in ('claude', 'codex') if getattr(args, a)]
    if not agents:
        agents = [a for a in ('claude', 'codex') if os.path.isdir(os.path.join(args.home, '.' + a))]
    if not agents:
        sys.exit('Neither ~/.claude nor ~/.codex exists. Pass --claude and/or --codex explicitly.')
    for agent in agents:
        configure(agent, args.home, args)
    print('Done. Start a new session to load it.' if not args.uninstall else 'Removed.')


if __name__ == '__main__':
    main()
