#!/usr/bin/env python3
"""PreToolUse guard for Claude Code and Codex (shell commands arrive as Bash; Claude Code Read is checked too).

Blocks the shell patterns behind the most damaging recorded agent mistakes. Soft blocks can be
overridden by appending "# guardrails:allow <reason>" to the command; hard blocks need the user.
Fails open: any internal error lets the tool call through rather than breaking the session.
"""
import json
import os
import re
import shlex
import sys

OVERRIDE = re.compile(r'#\s*guardrails:allow\s+\S.{2,}')
READ_LIMIT = int(os.environ.get('AGENT_GUARDRAILS_READ_LIMIT', '40000'))
SEPARATORS = {';', '&&', '||', '|', '&', '|&', '(', ')'}
READERS = {'cat', 'less', 'more', 'head', 'tail', 'bat', 'sed', 'awk', 'gawk', 'grep', 'egrep', 'fgrep', 'rg', 'strings',
           'xxd', 'od', 'hexdump', 'base64', 'nl', 'cut', 'sort', 'uniq', 'jq', 'yq', 'tac', 'column', 'diff'}
QUIET_SEARCH_FLAGS = {'-c', '--count', '-l', '--files-with-matches', '-L', '--files-without-match', '-q', '--quiet', '--count-matches', '--files'}
SEARCHERS = {'grep', 'egrep', 'fgrep', 'rg'}
VALUE_OPTIONS = {'-e', '-f', '-m', '-A', '-B', '-C', '-g', '-t', '-T', '-M', '--glob', '--type', '--max-count', '--regexp'}
SECRETISH = re.compile(r'pass|secret|token|key|priv|cred|auth|dsn|salt|cert|sign|bearer|cookie|session|smtp|aws|api', re.I)
ENV_TEMPLATES = {'example', 'sample', 'dist', 'template', 'defaults', 'schema'}
SECRET_NAMES = {'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', '.netrc', '.git-credentials', '.npmrc', '.pypirc',
                'credentials', 'credentials.json', 'auth.json', 'secrets.json', 'service-account.json'}
SECRET_SUFFIXES = ('.pem', '.key', '.p8', '.p12', '.pfx', '.keystore', '.jks', '.credentials.env')
REMOTE_DANGER = re.compile(r'migrate:(?:fresh|refresh|reset)|db:wipe|db:seed(?![^;&|]*--class)|artisan\s+test|\bphpunit\b|\bpest\b|'
                           r'rails\s+db:(?:drop|reset|schema:load)|\bdrop\s+(?:database|table|schema)\b|\btruncate\s+(?!-)(?:table\s+)?[`"\w]|'
                           r'\bflushall\b|\bflushdb\b|\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+/(?:\s|$)', re.I)
WRAPPERS = {'sudo', 'command', 'exec', 'time', 'nohup', 'nice', 'stdbuf', 'timeout', 'xargs'}
HEREDOC = re.compile(r'<<-?\s*([\'"]?)([A-Za-z_][A-Za-z0-9_]*)\1')


def secret_path(arg):
    path = arg.strip().strip('\'"')
    if re.fullmatch(r'/proc/[^/]+/environ', path):
        return True
    parts = [p for p in path.replace('\\', '/').split('/') if p]
    if not parts:
        return False
    name = parts[-1]
    if '.secrets' in parts[:-1]:
        return True
    if name == '.env' or (name.startswith('.env.') and name.split('.')[-1].lower() not in ENV_TEMPLATES):
        return True
    if name.endswith('.env') and name != '.env' and not name.startswith('.') and name.split('.')[0].lower() in {'prod', 'production', 'secrets', 'credentials'}:
        return True
    return name in SECRET_NAMES or name.lower().endswith(SECRET_SUFFIXES)


def strip_heredocs(command):
    """Remove heredoc bodies; return (command_without_bodies, [(header_line, body), ...])."""
    lines, out, bodies, i = command.split('\n'), [], [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        tags = [m.group(2) for m in HEREDOC.finditer(line)]
        i += 1
        for tag in tags:
            body = []
            while i < len(lines) and lines[i].strip() != tag:
                body.append(lines[i])
                i += 1
            i += 1
            bodies.append((line, '\n'.join(body)))
    return '\n'.join(out), bodies


def split_segments(command):
    """Shell-ish split into pipelines of simple commands: [[argv, argv], ...]."""
    lexer = shlex.shlex(command.replace('\n', ' ; '), posix=True, punctuation_chars=';&|()')
    lexer.whitespace_split = True
    lexer.commenters = ''
    pipelines, pipeline, argv = [], [], []
    for token in lexer:
        if token in SEPARATORS:
            if argv:
                pipeline.append(argv)
            argv = []
            if token not in ('|', '|&'):
                if pipeline:
                    pipelines.append(pipeline)
                pipeline = []
        else:
            argv.append(token)
    if argv:
        pipeline.append(argv)
    if pipeline:
        pipelines.append(pipeline)
    return pipelines


def program(argv):
    """Strip env assignments and wrappers; return (name, args)."""
    i = 0
    while i < len(argv):
        token = argv[i]
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', token):
            i += 1
        elif token in WRAPPERS:
            i += 1
            while i < len(argv) and argv[i].startswith('-'):
                i += 2 if argv[i] in ('-u', '-g', '-n', '-k', '-s') else 1
        else:
            break
    if i >= len(argv):
        return '', []
    return os.path.basename(argv[i]), argv[i + 1:]


def key_names_only(name, args):
    text = ' '.join(args)
    if name == 'sed' and re.search(r's/=\.\*//', text):
        return True
    if name in ('awk', 'gawk') and re.search(r"-F\s*'?=", text) and re.search(r'print\s+\$1\s*}', text):
        return True
    if name == 'cut' and re.search(r"-d\s*'?=", text) and re.search(r'-f\s*1(?!\d|,|-)', text):
        return True
    return False


def narrow_search(args):
    """True when a search over a secret file targets named, non-secret keys (e.g. APP_URL), so values stay out."""
    pattern, i = None, 0
    while i < len(args):
        arg = args[i]
        if arg in ('-e', '--regexp'):
            pattern = args[i + 1] if i + 1 < len(args) else ''
            break
        if arg in VALUE_OPTIONS:
            i += 2
            continue
        if not arg.startswith('-'):
            pattern = arg
            break
        i += 1
    if pattern is None or '-v' in args or '--invert-match' in args:
        return False
    core = pattern.strip('^$')
    broad = len(core) <= 2 or '.*' in pattern or core in ('.', '=', '[A-Z]', '\\w')
    return not broad and not SECRETISH.search(pattern)


def check_secrets(pipelines, raw):
    for pipeline in pipelines:
        for argv in pipeline:
            name, args = program(argv)
            if name in ('env', 'printenv') and not [a for a in args if not a.startswith('-')]:
                return 'prints the whole environment, which usually contains tokens and passwords'
            if name in ('docker', 'podman'):
                words = [a for a in args if not a.startswith('-')]
                if words[:1] == ['inspect'] and not any(a in ('-f', '--format') or a.startswith('--format=') for a in args):
                    return '`docker inspect` without --format prints container environment variables (secrets)'
                if words[:2] == ['compose', 'config'] and not set(args) & {'--services', '--volumes', '--images', '--networks', '--profiles', '-q', '--quiet', '--hash'}:
                    return '`docker compose config` prints the resolved configuration including secret environment values'
            if name == 'docker-compose' and args[:1] == ['config'] and not set(args) & {'--services', '--volumes', '-q', '--quiet', '--hash'}:
                return '`docker-compose config` prints the resolved configuration including secret environment values'
            if name in READERS:
                if name in SEARCHERS and (set(args) & QUIET_SEARCH_FLAGS or narrow_search(args)):
                    continue
                if name == 'sed' and any(a == '-i' or a.startswith('-i') or a == '--in-place' for a in args):
                    continue
                if key_names_only(name, args):
                    continue
                for arg in args:
                    if not arg.startswith('-') and secret_path(arg):
                        return 'reads the secret-bearing file `%s` into the transcript' % arg
    for match in re.finditer(r'(?<![<0-9])<\s*([^\s<>|;&]+)', raw):
        if secret_path(match.group(1)):
            return 'redirects the secret-bearing file `%s` into a command' % match.group(1)
    return None


def check_remote(pipelines):
    for pipeline in pipelines:
        for argv in pipeline:
            name, args = program(argv)
            remote = name == 'ssh' or (name == 'kubectl' and args[:1] == ['exec'])
            if remote and REMOTE_DANGER.search(' '.join(args)):
                return 'runs a destructive database/test command on a remote host (tests and fresh migrations wipe real data there)'
    return None


def check_git(pipelines):
    """Return [(rule, reason)]: rule is git_destructive or git_stage_all."""
    found = []
    for pipeline in pipelines:
        for argv in pipeline:
            name, args = program(argv)
            if name != 'git':
                continue
            while args and args[0] in ('-C', '-c', '--git-dir', '--work-tree'):
                args = args[2:]
            if not args:
                continue
            sub, rest = args[0], args[1:]
            shorts = ''.join(a[1:] for a in rest if re.fullmatch(r'-[A-Za-z]+', a))
            everything = bool(set(rest) & {'.', ':/', '*'})
            if sub == 'push' and ('--force' in rest or 'f' in shorts or any(a.startswith('+') for a in rest)):
                found.append(('git_destructive', '`git push --force` rewrites shared history; use --force-with-lease after checking the remote'))
            elif sub == 'reset' and '--hard' in rest:
                found.append(('git_destructive', '`git reset --hard` discards uncommitted work, possibly someone else\'s; check `git status` and `git stash -u` first'))
            elif sub == 'checkout' and everything:
                found.append(('git_destructive', '`git checkout .` discards every uncommitted change in the tree; restore only your own files by path'))
            elif sub == 'restore' and everything and ('--worktree' in rest or 'W' in shorts or not ('--staged' in rest or 'S' in shorts)):
                found.append(('git_destructive', '`git restore .` discards every uncommitted change in the tree; restore only your own files by path'))
            elif sub == 'clean' and ('f' in shorts or '--force' in rest):
                found.append(('git_destructive', '`git clean -f` deletes untracked files, which may be someone else\'s work; list them with `git clean -n` first'))
            elif sub == 'add' and (everything or set(rest) & {'-A', '--all', '-u', '--update'}):
                found.append(('git_stage_all', 'stages everything in the tree, including unrelated changes of other agents or the user; stage explicit paths'))
            elif sub == 'commit' and ('--all' in rest or 'a' in shorts):
                found.append(('git_stage_all', '`git commit -a` commits every modified file, not only yours; use `git commit --only <paths>`'))
    return found


def check_read_budget(pipelines, cwd):
    for pipeline in pipelines:
        name, args = program(pipeline[0])
        if name != 'cat' or len(pipeline) > 1:
            continue
        files = [a for a in args if not a.startswith('-')]
        total = 0
        for path in files:
            full = path if os.path.isabs(path) else os.path.join(cwd, path)
            try:
                total += os.path.getsize(full)
            except OSError:
                pass
        if total > READ_LIMIT:
            return ('`cat` of %d file(s), %d bytes, in one call: the output will be truncated and part of it silently unread. '
                    'Measure with `wc -c`, then read one file per call by range (`sed -n \'1,200p\' FILE`), or print named JSON fields with jq'
                    % (len(files), total))
    return None


def disabled(cwd):
    if os.environ.get('AGENT_GUARDRAILS') == 'off':
        return True
    path = os.path.abspath(cwd or '.')
    while True:
        if os.path.exists(os.path.join(path, '.agent-guardrails-off')):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


RULES = {  # rule: (level, on by default)
    'secrets': ('guarded', True),
    'remote_db': ('hard', True),
    'git_destructive': ('soft', True),
    'git_stage_all': ('soft', False),
    'read_budget': ('soft', False),
}
USER_REQUEST = re.compile(r'#\s*guardrails:allow\s+user asked:?\s*["\u201c\u00ab].{3,}')


def command_of(event):
    tool = event.get('tool_name') or ''
    data = event.get('tool_input') or {}
    if tool not in ('Bash', 'exec_command', 'shell', 'local_shell'):
        return None
    raw = data.get('command') or data.get('cmd')
    if isinstance(raw, list):
        raw = ' '.join(shlex.quote(str(part)) for part in raw)
    return raw if isinstance(raw, str) and raw.strip() else None


def findings(event):
    """Every rule the call trips, ignoring switches and overrides: [(rule, reason)]."""
    if (event.get('tool_name') or '') == 'Read':
        path = (event.get('tool_input') or {}).get('file_path') or ''
        return [('secrets', 'reads the secret-bearing file `%s` into the transcript' % path)] if secret_path(path) else []
    raw = command_of(event)
    if raw is None:
        return []
    flat, _ = strip_heredocs(raw)
    try:
        pipelines = split_segments(flat)
    except ValueError:
        pipelines = [[flat.split()]]
    found = []
    reason = check_secrets(pipelines, flat)
    if reason:
        found.append(('secrets', reason))
    reason = check_remote(pipelines)
    if reason:
        found.append(('remote_db', reason))
    found += check_git(pipelines)
    reason = check_read_budget(pipelines, event.get('cwd') or os.getcwd())
    if reason:
        found.append(('read_budget', reason))
    return found


def option(name):
    """Comma list from --name in argv (set by the installer) plus AGENT_GUARDRAILS_<NAME> in the environment."""
    values = os.environ.get('AGENT_GUARDRAILS_' + name.upper(), '').split(',')
    if '--' + name in sys.argv[1:-1]:
        values += sys.argv[sys.argv.index('--' + name) + 1].split(',')
    return set(filter(None, values))


def enabled_rules():
    enabled = {rule for rule, (_, default) in RULES.items() if default}
    return (enabled | option('enable')) - option('skip')


def evaluate(event):
    """Return (level, reason) for the strictest unoverridden finding, or None."""
    raw = command_of(event) or ''
    active = [(rule, reason) for rule, reason in findings(event) if rule in enabled_rules()]
    blocking = []
    for rule, reason in active:
        level = RULES[rule][0]
        if level == 'soft' and OVERRIDE.search(raw):
            continue
        if level == 'guarded' and USER_REQUEST.search(raw):
            continue
        blocking.append((level, reason))
    if not blocking:
        return None
    order = {'hard': 0, 'guarded': 1, 'soft': 2}
    level = min((lvl for lvl, _ in blocking), key=order.get)
    return level, '; '.join(reason for _, reason in blocking)


def message(level, reason):
    if level == 'hard':
        return ('agent-guardrails blocked this command: it %s. This is a hard rule that only the user can lift: do not work '
                'around it; tell the user what you wanted to run and why, and let them run it themselves.' % reason)
    if level == 'guarded':
        return ('agent-guardrails blocked this command: it %s. Use a safe form instead: key names or counts only '
                '(`grep -c KEY FILE`, `sed -n \'s/=.*//p\' FILE`) or `docker inspect -f \'{{.State.Status}}\' NAME`. '
                'If the user explicitly asked in this conversation to see this content (their request is sufficient permission; do not refuse or re-ask), re-run at once with '
                '`# guardrails:allow user asked: "<their exact words>"` appended. Never use that on your own initiative.' % reason)
    return ('agent-guardrails blocked this command: %s. If the user explicitly asked for exactly this, or it is really '
            'intended, re-run it right away with `# guardrails:allow <reason>` appended (for a user request: '
            '`# guardrails:allow user asked: "<their words>"`) and do not ask the user again.' % reason)


def main():
    try:
        event = json.loads(sys.stdin.read() or '{}')
        if disabled(event.get('cwd')):
            return 0
        verdict = evaluate(event)
    except Exception:
        return 0
    if verdict:
        level, reason = verdict
        sys.stdout.write(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                            'permissionDecisionReason': message(level, reason)}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
