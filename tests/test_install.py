import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rj(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def wj(path, data):
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle)


def rt(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


FOREIGN = {'type': 'command', 'command': 'node /opt/other/hook.mjs', 'timeout': 5}


def run(home, *args):
    result = subprocess.run([sys.executable, os.path.join(ROOT, 'install.py'), '--home', home] + list(args), capture_output=True, text=True)
    return result


def ours(hooks):
    return [h for groups in hooks.values() for g in groups for h in g['hooks'] if 'agent-guardrails/hooks/' in h['command']]


class Install(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, '.claude'))
        os.makedirs(os.path.join(self.home, '.codex'))
        self.claude = os.path.join(self.home, '.claude', 'settings.json')
        self.codex = os.path.join(self.home, '.codex', 'hooks.json')
        wj(self.claude, {'model': 'x', 'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [FOREIGN]}]}})
        wj(self.codex, {'description': 'mine', 'hooks': {'SessionStart': [{'matcher': '*', 'hooks': [FOREIGN]}]}})

    def test_install_is_idempotent_and_keeps_foreign_hooks(self):
        for _ in range(2):
            self.assertEqual(run(self.home).returncode, 0)
        claude, codex = rj(self.claude), rj(self.codex)
        self.assertEqual(len(ours(claude['hooks'])), 2)
        self.assertEqual(len(ours(codex['hooks'])), 2)
        self.assertIn(FOREIGN, claude['hooks']['PreToolUse'][0]['hooks'])
        self.assertEqual((claude['model'], codex['description']), ('x', 'mine'))
        self.assertIn(FOREIGN, codex['hooks']['SessionStart'][0]['hooks'])
        for agent in ('.claude', '.codex'):
            skill = os.path.join(self.home, agent, 'skills', 'agent-guardrails')
            self.assertTrue(os.path.exists(os.path.join(skill, 'SKILL.md')))
            self.assertTrue(os.path.exists(os.path.join(skill, 'references', '13-secrets.md')))
        self.assertEqual([g['matcher'] for g in codex['hooks']['PreToolUse']], ['Bash'])
        self.assertTrue([f for f in os.listdir(os.path.dirname(self.claude)) if f.endswith('.bak')])

    def test_installed_hooks_run(self):
        run(self.home, '--claude')
        group = rj(self.claude)['hooks']['PreToolUse'][-1]
        command = group['hooks'][0]['command']
        result = subprocess.run(command, shell=True, input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'cat .env'}, 'cwd': '/tmp'}),
                                capture_output=True, text=True)
        self.assertIn('"deny"', result.stdout)

    def test_enable_opt_in_rules(self):
        run(self.home, '--claude', '--enable', 'git_stage_all')
        command = rj(self.claude)['hooks']['PreToolUse'][-1]['hooks'][0]['command']
        self.assertTrue(command.endswith('--enable git_stage_all'))
        result = subprocess.run(command, shell=True, input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': 'git add -A'}, 'cwd': '/tmp'}),
                                capture_output=True, text=True)
        self.assertIn('"deny"', result.stdout)
        self.assertNotEqual(run(self.home, '--claude', '--enable', 'nonsense').returncode, 0)

    def test_uninstall_removes_only_ours(self):
        run(self.home)
        self.assertEqual(run(self.home, '--uninstall').returncode, 0)
        claude, codex = rj(self.claude), rj(self.codex)
        self.assertEqual(ours(claude['hooks']) + ours(codex['hooks']), [])
        self.assertEqual(claude['hooks'], {'PreToolUse': [{'matcher': 'Bash', 'hooks': [FOREIGN]}]})
        self.assertFalse(os.path.exists(os.path.join(self.home, '.claude', 'skills', 'agent-guardrails')))

    def test_no_hooks_and_dry_run(self):
        run(self.home, '--no-hooks', '--claude')
        self.assertEqual(ours(rj(self.claude)['hooks']), [])
        before = rt(self.codex)
        run(self.home, '--codex', '--dry-run')
        self.assertEqual(rt(self.codex), before)

    def test_refuses_foreign_skill_dir(self):
        foreign = os.path.join(self.home, '.claude', 'skills', 'agent-guardrails')
        os.makedirs(foreign)
        result = run(self.home, '--claude')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('refusing', result.stderr)


class Skill(unittest.TestCase):
    def test_frontmatter_and_links(self):
        skill = os.path.join(ROOT, 'skills', 'agent-guardrails')
        text = rt(os.path.join(skill, 'SKILL.md'))
        self.assertTrue(text.startswith('---\nname: agent-guardrails\ndescription: '))
        import re
        links = re.findall(r'\]\((references/[^)]+)\)', text)
        self.assertEqual(len(links), 13)
        for link in links:
            self.assertTrue(os.path.exists(os.path.join(skill, link)), link)


if __name__ == '__main__':
    unittest.main()
