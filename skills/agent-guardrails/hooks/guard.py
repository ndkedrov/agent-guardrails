#!/usr/bin/env python3
"""PreToolUse guard for Claude Code (Bash, Read) and Codex (exec_command).

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
           'xxd', 'od', 'hexdump', 'base64', 'nl', 'cut', 'sort', 'uniq', 'jq', 'yq', 'tac', 'column', 'diff', 'cp', 'scp', 'open'}
QUIET_SEARCH_FLAGS = {'-c', '--count', '-l', '--files-with-matches', '-L', '--files-without-match', '-q', '--quiet', '--count-matches'}
ENV_TEMPLATES = {'example', 'sample', 'dist', 'template', 'defaults', 'schema'}
SECRET_NAMES = {'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', '.netrc', '.git-credentials', '.npmrc', '.pypirc',
                'credentials', 'credentials.json', 'auth.json', 'secrets.json', 'service-account.json'}
SECRET_SUFFIXES = ('.pem', '.key', '.p8', '.p12', '.pfx', '.keystore', '.jks', '.credentials.env')
REMOTE_DANGER = re.compile(r'migrate:(?:fresh|refresh|reset)|db:wipe|db:seed|artisan\s+test|\bphpunit\b|\bpest\b|'
                           r'rails\s+db:(?:drop|reset|schema:load)|\bdrop\s+(?:database|table|schema)\b|\btruncate\b|'
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
                if name in ('grep', 'egrep', 'fgrep', 'rg') and set(args) & QUIET_SEARCH_FLAGS:
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
            if sub == 'push' and ('--force' in rest or 'f' in shorts or any(a.startswith('+') for a in rest)):
                return ('soft', '`git push --force` rewrites shared history. Use --force-with-lease after checking the remote, or ask the user')
            if sub == 'reset' and '--hard' in rest:
                return ('soft', '`git reset --hard` discards uncommitted work, possibly someone else\'s. Run `git status` and `git stash -u` first')
            if sub in ('checkout', 'restore') and ('.' in rest or ':/' in rest) :
                return ('soft', '`git %s .` discards all uncommitted changes in the tree. Restore only your own files by path' % sub)
            if sub == 'checkout' and '--' in rest and rest.index('--') == len(rest) - 1:
                return ('soft', '`git checkout --` without paths is ambiguous and destructive')
            if sub == 'clean' and ('f' in shorts or '--force' in rest):
                return ('soft', '`git clean -f` deletes untracked files, which may be someone else\'s work. List them with `git clean -n` first')
            if sub == 'branch' and ('-D' in rest or ('--delete' in rest and '--force' in rest)):
                return ('soft', '`git branch -D` deletes an unmerged branch')
            if sub == 'stash' and rest[:1] in (['drop'], ['clear']):
                return ('soft', '`git stash %s` permanently drops stashed work' % rest[0])
            if sub == 'add' and (set(rest) & {'-A', '--all', '.', ':/', '*', '-u', '--update'}):
                return ('soft', 'stages everything in the tree, including other agents\' or the user\'s unrelated changes. Stage explicit paths')
            if sub == 'commit' and ('--all' in rest or 'a' in shorts):
                return ('soft', '`git commit -a` commits every modified file, not only yours. Use `git commit --only <paths>` or stage explicit paths')
    return None


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
        if total > READ_LIMIT or len(files) >= 4:
            return ('`cat` of %d file(s), %d bytes, in one call: the output will be truncated and part of it silently unread. '
                    'Measure with `wc -c`, then read one file per call by range (`sed -n \'1,200p\' FILE`), or print named JSON fields with jq'
                    % (len(files), total))
    return None


def check_python_stdin(bodies, pipelines):
    for header, body in bodies:
        if re.search(r'\bpython[0-9.]*\b(?:\s+-[A-Za-z]+)*(?:\s+-)?\s*<<', header) and re.search(r'[^\x00-\x7f]', body):
            return 'pipes non-ASCII Python source through stdin; this shell is not guaranteed to be UTF-8 and fails with SyntaxError'
    for pipeline in pipelines:
        for argv in pipeline:
            name, args = program(argv)
            if re.fullmatch(r'python[0-9.]*', name) and '-c' in args:
                code = args[args.index('-c') + 1] if args.index('-c') + 1 < len(args) else ''
                if re.search(r'[^\x00-\x7f]', code):
                    return 'passes non-ASCII Python source via -c; this shell is not guaranteed to be UTF-8 and fails with SyntaxError'
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


def evaluate(event):
    """Return (level, message) or None. level: 'hard' | 'soft'."""
    tool = event.get('tool_name') or ''
    data = event.get('tool_input') or {}
    cwd = event.get('cwd') or os.getcwd()
    skip = set(filter(None, os.environ.get('AGENT_GUARDRAILS_SKIP', '').split(',')))
    if tool == 'Read':
        path = data.get('file_path') or ''
        if 'secrets' not in skip and secret_path(path):
            return ('hard', 'reads the secret-bearing file `%s` into the transcript' % path)
        return None
    if tool not in ('Bash', 'exec_command', 'shell', 'local_shell'):
        return None
    raw = data.get('command') if tool == 'Bash' else (data.get('cmd') or data.get('command'))
    if isinstance(raw, list):
        raw = ' '.join(shlex.quote(str(part)) for part in raw)
    if not isinstance(raw, str) or not raw.strip():
        return None
    flat, bodies = strip_heredocs(raw)
    try:
        pipelines = split_segments(flat)
    except ValueError:
        pipelines = [[flat.split()]]
    if 'secrets' not in skip:
        reason = check_secrets(pipelines, flat)
        if reason:
            return ('hard', reason)
    if 'remote' not in skip:
        reason = check_remote(pipelines)
        if reason:
            return ('hard', reason)
    soft = []
    if 'git' not in skip:
        found = check_git(pipelines)
        if found:
            soft.append(found[1])
    if 'read_budget' not in skip:
        found = check_read_budget(pipelines, cwd)
        if found:
            soft.append(found)
    if 'python_stdin' not in skip and tool != 'Bash':
        found = check_python_stdin(bodies, pipelines)
        if found:
            soft.append(found + '. Write the script to a file with the file-editing tool, then run `python3 FILE`')
    if soft and not OVERRIDE.search(raw):
        return ('soft', '; '.join(soft))
    return None


def message(level, reason):
    if level == 'hard':
        return ('agent-guardrails blocked this command: it %s. This is a hard rule. Do not work around it; '
                'ask the user to run it or to change the rule. Safe alternatives: print key names or counts only '
                '(`grep -c KEY FILE`, `sed -n \'s/=.*//p\' FILE`), or `docker inspect -f \'{{.State.Status}}\' NAME`.' % reason)
    return ('agent-guardrails blocked this command: %s. If it is really intended, re-run it with '
            '`# guardrails:allow <reason>` appended, and mention the reason to the user.' % reason)


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
