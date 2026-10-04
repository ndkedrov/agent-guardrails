import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, 'skills', 'agent-guardrails', 'hooks')
sys.path.insert(0, HOOKS)
import guard  # noqa: E402


def verdict(command, tool='Bash', cwd=None):
    key = 'command' if tool == 'Bash' else 'cmd'
    return guard.evaluate({'tool_name': tool, 'tool_input': {key: command}, 'cwd': cwd or tempfile.gettempdir()})


class Secrets(unittest.TestCase):
    def test_blocks_reading_secret_files(self):
        for command in ['cat .env', 'cat backend/.env.production', 'head -5 ~/.ssh/id_ed25519', 'grep DB_PASSWORD .env',
                        'rg TOKEN config/.env.local', 'cat certs/server.key', 'less AuthKey_ABC.p8', 'jq . credentials.json',
                        'cat .secrets/app.credentials.env', 'cat /proc/1/environ', 'python3 x.py < .env', 'cp .env /tmp/x']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'hard')

    def test_blocks_environment_dumps(self):
        for command in ['env', 'printenv', 'env | sort', 'docker inspect app', 'docker compose config',
                        'docker-compose config', 'sudo docker inspect db']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'hard')

    def test_allows_safe_forms(self):
        for command in ['cat .env.example', 'cat .env.sample', 'grep -c DB_ .env', 'rg -l TOKEN .', 'grep -q KEY .env',
                        "sed -n 's/=.*//p' .env", "awk -F= '{print $1}' .env", 'cut -d= -f1 .env', 'printenv HOME',
                        'env FOO=1 make test', "docker inspect -f '{{.State.Status}}' app", 'docker compose config --services',
                        'cat id_ed25519.pub', 'ls -la .env', 'test -f .env && echo yes', 'git diff -- src/env.ts']:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_read_tool(self):
        self.assertEqual(guard.evaluate({'tool_name': 'Read', 'tool_input': {'file_path': '/app/.env'}})[0], 'hard')
        self.assertIsNone(guard.evaluate({'tool_name': 'Read', 'tool_input': {'file_path': '/app/README.md'}}))

    def test_override_does_not_unlock_hard_rules(self):
        self.assertEqual(verdict('cat .env # guardrails:allow need it')[0], 'hard')


class Remote(unittest.TestCase):
    def test_blocks_destructive_remote(self):
        for command in ["ssh prod 'cd /srv/app && php artisan test'", 'ssh root@host docker exec app php artisan migrate:fresh',
                        "ssh db 'mysql -e \"DROP DATABASE shop\"'", 'kubectl exec api -- php artisan db:wipe',
                        "ssh h 'php artisan db:seed --force'"]:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'hard')

    def test_allows_local_and_safe_remote(self):
        for command in ['docker exec -u www-data app php artisan test', 'php artisan migrate:fresh --seed',
                        "ssh prod 'php artisan migrate --force'", "ssh prod 'tail -n 50 /var/log/app.log'"]:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))


class Git(unittest.TestCase):
    def test_soft_blocks(self):
        for command in ['git push --force origin main', 'git push -f', 'git reset --hard HEAD~1', 'git checkout .',
                        'git restore .', 'git clean -fdx', 'git add -A', 'git add .', 'git commit -am "wip"',
                        'git commit --all -m x', 'git branch -D feature', 'git stash drop', 'git -C repo add --all']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'soft')

    def test_allows_normal_git(self):
        for command in ['git push --force-with-lease', 'git add src/a.py tests/test_a.py', 'git commit --only a.py -m "fix"',
                        'git commit -m "add all the things"', 'git commit --amend -m x', 'git checkout -b feature',
                        'git restore src/a.py', 'git clean -n', 'git status --short', 'git stash -u', 'git reset --soft HEAD~1']:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_override(self):
        self.assertIsNone(verdict('git reset --hard origin/main # guardrails:allow user asked to discard local edits'))
        self.assertEqual(verdict('git reset --hard # guardrails:allow')[0], 'soft')


class ReadBudget(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for name, size in [('big.json', 60000), ('a.md', 100), ('b.md', 100), ('c.md', 100), ('d.md', 100)]:
            with open(os.path.join(self.dir, name), 'w') as handle:
                handle.write('x' * size)

    def test_blocks_large_or_many(self):
        self.assertEqual(verdict('cat big.json', cwd=self.dir)[0], 'soft')
        self.assertEqual(verdict('cat a.md b.md c.md d.md', cwd=self.dir)[0], 'soft')

    def test_allows_small_or_limited(self):
        self.assertIsNone(verdict('cat a.md b.md', cwd=self.dir))
        self.assertIsNone(verdict('cat big.json | head -c 2000', cwd=self.dir))
        self.assertIsNone(verdict('cat missing.txt', cwd=self.dir))


class PythonStdin(unittest.TestCase):
    def test_codex_blocks_non_ascii_stdin_source(self):
        self.assertEqual(verdict("python3 - <<'PY'\nprint('привіт')\nPY", tool='exec_command')[0], 'soft')
        self.assertEqual(verdict("python3 -c \"print('привіт')\"", tool='exec_command')[0], 'soft')

    def test_codex_allows_ascii_and_data_heredocs(self):
        self.assertIsNone(verdict("python3 - <<'PY'\nprint('hi')\nPY", tool='exec_command'))
        self.assertIsNone(verdict("python3 tool.py <<'JSON'\n{\"t\": \"привіт\"}\nJSON", tool='exec_command'))

    def test_claude_is_not_affected(self):
        self.assertIsNone(verdict("python3 - <<'PY'\nprint('привіт')\nPY"))

    def test_heredoc_body_is_not_parsed_as_commands(self):
        self.assertIsNone(verdict("cat > notes.md <<'EOF'\nnever run cat .env or git add -A\nEOF"))


class Plumbing(unittest.TestCase):
    def run_hook(self, event, env=None):
        result = subprocess.run([sys.executable, os.path.join(HOOKS, 'guard.py')], input=json.dumps(event).encode(),
                                capture_output=True, env=dict(os.environ, **(env or {})))
        self.assertEqual(result.returncode, 0)
        return result.stdout.decode()

    def test_deny_output_shape(self):
        out = json.loads(self.run_hook({'tool_name': 'Bash', 'tool_input': {'command': 'cat .env'}, 'cwd': '/tmp'}))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIn('hard rule', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_codex_shape_and_list_command(self):
        out = self.run_hook({'tool_name': 'exec_command', 'tool_input': {'cmd': ['git', 'add', '-A']}, 'cwd': '/tmp'})
        self.assertIn('deny', out)

    def test_allows_silently(self):
        self.assertEqual(self.run_hook({'tool_name': 'Bash', 'tool_input': {'command': 'ls'}, 'cwd': '/tmp'}), '')

    def test_kill_switches(self):
        event = {'tool_name': 'Bash', 'tool_input': {'command': 'cat .env'}, 'cwd': tempfile.mkdtemp()}
        self.assertEqual(self.run_hook(event, {'AGENT_GUARDRAILS': 'off'}), '')
        open(os.path.join(event['cwd'], '.agent-guardrails-off'), 'w').close()
        self.assertEqual(self.run_hook(event), '')

    def test_fails_open_on_garbage(self):
        result = subprocess.run([sys.executable, os.path.join(HOOKS, 'guard.py')], input=b'not json', capture_output=True)
        self.assertEqual((result.returncode, result.stdout), (0, b''))

    def test_session_start_digest(self):
        result = subprocess.run([sys.executable, os.path.join(HOOKS, 'session_start.py')], input=b'{}', capture_output=True)
        context = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
        self.assertIn('AGENT GUARDRAILS', context)
        self.assertLessEqual(len(context), 2900)


if __name__ == '__main__':
    unittest.main()
