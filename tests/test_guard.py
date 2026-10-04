import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, 'skills', 'agent-guardrails', 'hooks')
sys.path.insert(0, HOOKS)
import guard  # noqa: E402


def verdict(command, cwd=None, **env):
    with mock.patch.dict(os.environ, env):
        return guard.evaluate({'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': cwd or tempfile.gettempdir()})


class Secrets(unittest.TestCase):
    def test_blocks_reading_secret_values(self):
        for command in ['cat .env', 'cat backend/.env.production', 'head -5 ~/.ssh/id_ed25519', 'grep DB_PASSWORD .env',
                        'grep -n . .env', 'grep -E "APP_KEY|DB_HOST" .env', 'rg TOKEN config/.env.local', 'grep -v "#" .env',
                        'cat certs/server.key', 'less AuthKey_ABC.p8', 'jq . credentials.json', 'cat .secrets/app.credentials.env',
                        'cat /proc/1/environ', 'python3 x.py < .env']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'guarded')

    def test_blocks_environment_dumps(self):
        for command in ['env', 'printenv', 'env | sort', 'docker inspect app', 'docker compose config', 'docker-compose config',
                        'sudo docker inspect db']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'guarded')

    def test_allows_routine_forms(self):
        for command in ['cat .env.example', 'cp .env.example .env', 'cp .env .env.bak', "sed -i '' 's/DEBUG=true/DEBUG=false/' .env",
                        'grep -E "APP_URL|APP_ENV" .env', 'grep -n QUEUE_CONNECTION .env', 'grep -c DB_ .env', 'rg -l TOKEN .',
                        "rg --files -g '*.p8'", 'grep -q KEY .env', "sed -n 's/=.*//p' .env", "awk -F= '{print $1}' .env",
                        'cut -d= -f1 .env', 'printenv HOME', 'env FOO=1 make test', "docker inspect -f '{{.State.Status}}' app",
                        'docker compose config --services', 'cat id_ed25519.pub', 'ls -la .env', 'test -f .env && echo yes']:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_read_tool(self):
        self.assertEqual(guard.evaluate({'tool_name': 'Read', 'tool_input': {'file_path': '/app/.env'}})[0], 'guarded')
        self.assertIsNone(guard.evaluate({'tool_name': 'Read', 'tool_input': {'file_path': '/app/README.md'}}))

    def test_user_request_unlocks_with_quote_only(self):
        self.assertIsNone(verdict('cat .env # guardrails:allow user asked: "покажи мені весь .env"'))
        self.assertEqual(verdict('cat .env # guardrails:allow I need it')[0], 'guarded')
        self.assertEqual(verdict('cat .env # guardrails:allow user asked')[0], 'guarded')


class Remote(unittest.TestCase):
    def test_blocks_destructive_remote(self):
        for command in ["ssh prod 'cd /srv/app && php artisan test'", 'ssh root@host docker exec app php artisan migrate:fresh',
                        "ssh db 'mysql -e \"DROP DATABASE shop\"'", "ssh db 'mysql -e \"TRUNCATE TABLE orders\"'",
                        'kubectl exec api -- php artisan db:wipe', "ssh h 'php artisan db:seed --force'"]:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'hard')

    def test_allows_local_and_routine_remote(self):
        for command in ['docker exec -u www-data app php artisan test', 'php artisan migrate:fresh --seed',
                        "ssh prod 'php artisan migrate --force'", "ssh prod 'php artisan db:seed --class=CitySeeder --force'",
                        "ssh prod 'truncate -s 0 /var/log/app.log'", "ssh prod 'tail -n 50 /var/log/app.log'"]:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_hard_ignores_overrides(self):
        self.assertEqual(verdict("ssh prod 'php artisan test' # guardrails:allow user asked: \"run tests on prod\"")[0], 'hard')


class Git(unittest.TestCase):
    def test_destructive_is_soft_blocked(self):
        for command in ['git push --force origin main', 'git push -f', 'git reset --hard HEAD~1', 'git checkout .',
                        'git restore .', 'git clean -fdx']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command)[0], 'soft')

    def test_routine_git_passes(self):
        for command in ['git push --force-with-lease', 'git add -A', 'git add .', 'git commit -am "wip"', 'git add src/a.py',
                        'git commit --amend -m x', 'git checkout -b feature', 'git restore src/a.py', 'git restore --staged .',
                        'git clean -n', 'git status --short', 'git stash -u', 'git stash drop', 'git branch -D old-feature',
                        'git reset --soft HEAD~1', 'git commit -m "add all the things"']:
            with self.subTest(command=command):
                self.assertIsNone(verdict(command))

    def test_stage_all_is_opt_in(self):
        for command in ['git add -A', 'git add .', 'git commit -am "wip"', 'git -C repo add --all']:
            with self.subTest(command=command):
                self.assertEqual(verdict(command, AGENT_GUARDRAILS_ENABLE='git_stage_all')[0], 'soft')

    def test_override(self):
        self.assertIsNone(verdict('git reset --hard origin/main # guardrails:allow user asked: "скинь до origin"'))
        self.assertIsNone(verdict('git reset --hard origin/main # guardrails:allow mirror clone, no local work'))
        self.assertEqual(verdict('git reset --hard # guardrails:allow')[0], 'soft')

    def test_skip(self):
        self.assertIsNone(verdict('git reset --hard', AGENT_GUARDRAILS_SKIP='git_destructive'))


class ReadBudget(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, 'big.json'), 'w') as handle:
            handle.write('x' * 60000)

    def test_off_by_default(self):
        self.assertIsNone(verdict('cat big.json', cwd=self.dir))

    def test_opt_in(self):
        self.assertEqual(verdict('cat big.json', cwd=self.dir, AGENT_GUARDRAILS_ENABLE='read_budget')[0], 'soft')
        self.assertIsNone(verdict('cat big.json | head -c 2000', cwd=self.dir, AGENT_GUARDRAILS_ENABLE='read_budget'))


class Parsing(unittest.TestCase):
    def test_heredoc_body_is_not_parsed_as_commands(self):
        self.assertIsNone(verdict("cat > notes.md <<'EOF'\nnever run cat .env or git reset --hard\nEOF"))

    def test_non_ascii_python_stdin_is_allowed(self):
        self.assertIsNone(verdict("python3 - <<'PY'\nprint('привіт')\nPY"))


class Plumbing(unittest.TestCase):
    def run_hook(self, event, env=None):
        result = subprocess.run([sys.executable, os.path.join(HOOKS, 'guard.py')], input=json.dumps(event).encode(),
                                capture_output=True, env=dict(os.environ, **(env or {})))
        self.assertEqual(result.returncode, 0)
        return result.stdout.decode()

    def test_deny_output_shape(self):
        out = json.loads(self.run_hook({'tool_name': 'Bash', 'tool_input': {'command': 'git reset --hard'}, 'cwd': '/tmp'}))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIn('user explicitly asked', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_codex_list_command(self):
        self.assertIn('deny', self.run_hook({'tool_name': 'Bash', 'tool_input': {'command': ['git', 'reset', '--hard']}, 'cwd': '/tmp'}))

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
        with open(os.path.join(ROOT, 'skills', 'agent-guardrails', 'DIGEST.md'), encoding='utf-8') as handle:
            self.assertEqual(context, handle.read().strip(), 'DIGEST.md must fit the 2900-char hook limit untruncated')


if __name__ == '__main__':
    unittest.main()
