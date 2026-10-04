# agent-guardrails

**A skill and two hooks that stop coding agents (Claude Code and Codex) from repeating the mistakes they make most often.**

[English](#english) · [Українська](#українська)

---

## English

### Why this exists

Coding agents working on real mobile, desktop, web and backend projects were required to log every mistake they made into a private journal, right when it happened: 1,156 incidents in total. Each incident was read and classified by its primary cause. The same handful of mistakes accounts for most of them:

| # | Category | Incidents | Share |
|---|----------|----------:|------:|
| 01 | Guessed file paths and wrong working directory | 204 | 17.6% |
| 02 | Oversized reads, truncated output | 190 | 16.4% |
| 03 | Logic bugs in product code (failure paths, stale async results, wrong types) | 142 | 12.3% |
| 04 | Shell / CLI / tool misuse | 136 | 11.8% |
| 05 | Guessed JSON, SQL and API shapes | 113 | 9.8% |
| 06 | Wrong order of work, scope creep, shared/production environments | 80 | 6.9% |
| 07 | Broken formal protocols (handoffs, reports, descriptors) | 79 | 6.8% |
| 08 | Weak tests that cannot fail | 57 | 4.9% |
| 09 | Unverified or false claims | 52 | 4.5% |
| 10 | UI defects and flaky UI tests | 34 | 2.9% |
| 11 | Delegation briefs for sub-agents | 32 | 2.8% |
| 12 | Requirements silently left out | 22 | 1.9% |
| 13 | Secrets printed into output | 13 | 1.1% |

Most of these are cheap to prevent. Promises like "next time I will read narrowly" are not enough: in many incidents the agent made the same promise before and broke it again. This repository turns the lessons into something agents load in **every session**, plus hooks that **mechanically block** the most damaging patterns.

### What is inside

```
skills/agent-guardrails/
  SKILL.md            the 13 rules + "before the first action" and "before you say done" checklists
  DIGEST.md           a 2.4 KB digest injected at every session start, resume and compaction
  references/01..13   per category: subtypes, root causes, costs, prevention measures, checklists
  hooks/session_start.py   SessionStart hook: injects DIGEST.md
  hooks/guard.py           PreToolUse hook: blocks dangerous shell commands (see below)
install.py            installs or updates or removes everything for Claude Code and/or Codex
tests/                unit tests for the guard and the installer
```

The skill is the same file for both agents: Claude Code and Codex both read `SKILL.md` with `name`/`description` front matter from their `skills/` directory.

### Install

Requirements: Python 3.8+ (standard library only), Claude Code and/or Codex.

```bash
git clone https://github.com/ndkedrov/agent-guardrails.git
cd agent-guardrails
python3 install.py
```

By default the installer configures every agent it finds (`~/.claude`, `~/.codex`):

- copies the skill to `~/.claude/skills/agent-guardrails` and `~/.codex/skills/agent-guardrails`;
- registers the SessionStart and PreToolUse hooks in `~/.claude/settings.json` and `~/.codex/hooks.json`;
- backs up each settings file before changing it, and never touches hooks that are not its own.

Options: `--claude`, `--codex`, `--no-hooks` (skill only), `--dry-run`, `--uninstall`. To update, run `git pull && python3 install.py`.

**Codex:** Codex runs new or changed hooks only after you review and trust them. Open Codex after installing and approve the two `agent-guardrails` hooks.

Start a new session afterwards; running sessions do not pick up a new skill.

#### Without hooks

If you prefer not to install hooks, use `--no-hooks` and paste the contents of `skills/agent-guardrails/DIGEST.md` into your global instructions (`~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`). The rules then load every session; nothing is enforced mechanically.

### What the guard blocks

`hooks/guard.py` inspects shell commands (`Bash` in Claude Code, `exec_command` in Codex) and Claude Code's `Read` tool.

| Level | Blocks | Why |
|-------|--------|-----|
| hard | Reading `.env*` (not `.env.example`), private keys, `*.pem/*.key/*.p8/*.p12`, credential files, `/proc/*/environ`; bare `env`/`printenv`; `docker inspect` without `--format`; `docker compose config` | secrets end up in the transcript |
| hard | Over `ssh` or `kubectl exec`: test suites, `migrate:fresh/refresh/reset`, `db:wipe`, `db:seed`, `DROP`, `TRUNCATE`, `FLUSHALL` | tests and fresh migrations wipe real data |
| soft | `git push --force`, `reset --hard`, `checkout .`, `restore .`, `clean -f`, `branch -D`, `stash drop/clear` | discards work, possibly someone else's |
| soft | `git add -A/./--all/-u`, `git commit -a` | commits other people's changes |
| soft | `cat` of files larger than 40 KB in total, or of 4+ files, without a limiting pipe | output gets truncated and is silently unread |
| soft (Codex only) | Non-ASCII Python source through `python3 -` / `-c` | non-UTF-8 agent shells fail with `SyntaxError` |

Safe forms stay allowed. For example, `grep -c KEY .env`, `sed -n 's/=.*//p' .env` (key names only), `docker inspect -f '{{.State.Status}}' app`, and running tests locally with `docker exec app php artisan test`.

- **Soft blocks** can be overridden deliberately by appending `# guardrails:allow <reason>` to the command. The agent is told to mention the reason to you.
- **Hard blocks** cannot be overridden by the agent.
- **Switches:**
  - `AGENT_GUARDRAILS=off` in the agent's environment disables everything.
  - A file named `.agent-guardrails-off` in a project (or any parent directory) disables it for that tree.
  - `AGENT_GUARDRAILS_SKIP=secrets,remote,git,read_budget,python_stdin` skips individual checks.
  - `AGENT_GUARDRAILS_READ_LIMIT=<bytes>` changes the read budget.
- **Fail-open:** if the guard itself fails, the command goes through. A broken guard should never block your session.

### Limitations

- The guard is a heuristic, not a sandbox. A determined command can still get around it. It exists to catch the habitual mistakes, not adversaries.
- 1,145 of the incidents were logged by Codex and 11 by Claude Code. The rules are agent-agnostic, but the statistics mainly reflect Codex's habits.
- No incident texts are published. They described private projects, so only aggregated categories and generalized lessons are included.

### Tests

```bash
python3 -m unittest discover -s tests
```

### License

MIT

---

## Українська

### Навіщо це

ШІ-агенти, що працювали над реальними мобільними, десктопними, вебовими й серверними проєктами, мали записувати кожну свою помилку в приватний журнал одразу, як вона ставалась: разом 1 156 інцидентів. Кожен інцидент прочитано й віднесено до категорії за першопричиною. Більшість припадає на невеликий набір одних і тих самих помилок:

| # | Категорія | Інцидентів | Частка |
|---|-----------|-----------:|-------:|
| 01 | Вгадані шляхи до файлів і хибна робоча тека | 204 | 17,6% |
| 02 | Надто великі читання, обрізаний вивід | 190 | 16,4% |
| 03 | Логічні помилки в продуктовому коді (гілки збою, застарілі async-результати, не ті типи) | 142 | 12,3% |
| 04 | Хибне використання shell, CLI та інструментів | 136 | 11,8% |
| 05 | Вгадана структура JSON, SQL та API | 113 | 9,8% |
| 06 | Порушений порядок роботи, вихід за скоуп, спільні й бойові середовища | 80 | 6,9% |
| 07 | Порушені формальні протоколи (handoff, звіти, дескриптори) | 79 | 6,8% |
| 08 | Слабкі тести, які не можуть впасти | 57 | 4,9% |
| 09 | Неперевірені чи хибні твердження | 52 | 4,5% |
| 10 | Дефекти UI та нестабільні UI-тести | 34 | 2,9% |
| 11 | Брифи для субагентів | 32 | 2,8% |
| 12 | Мовчки пропущені вимоги | 22 | 1,9% |
| 13 | Секрети у виводі | 13 | 1,1% |

Більшості з них дешево запобігти. Обіцянок на кшталт «наступного разу читатиму вузько» недостатньо: у багатьох інцидентах агент уже давав таку саму обіцянку раніше й знову її порушував. Цей репозиторій перетворює уроки на те, що агенти завантажують у **кожній сесії**, плюс хуки, які **механічно блокують** найшкідливіші патерни.

### Що всередині

```
skills/agent-guardrails/
  SKILL.md            13 правил + чеклисти «перед першою дією» і «перед тим, як сказати готово»
  DIGEST.md           дайджест на 2,4 КБ, що додається на старті, відновленні й ущільненні кожної сесії
  references/01..13   по кожній категорії: підтипи, корені, наслідки, заходи запобігання, чеклисти
  hooks/session_start.py   хук SessionStart: додає DIGEST.md у контекст
  hooks/guard.py           хук PreToolUse: блокує небезпечні shell-команди (див. нижче)
install.py            встановлює, оновлює чи видаляє все для Claude Code та/або Codex
tests/                юніт-тести сторожа та інсталятора
```

Скіл — той самий файл для обох агентів: і Claude Code, і Codex читають `SKILL.md` з полями `name`/`description` зі своєї теки `skills/`.

### Встановлення

Потрібно: Python 3.8+ (лише стандартна бібліотека), Claude Code та/або Codex.

```bash
git clone https://github.com/ndkedrov/agent-guardrails.git
cd agent-guardrails
python3 install.py
```

За замовчуванням інсталятор налаштовує кожного знайденого агента (`~/.claude`, `~/.codex`):

- копіює скіл у `~/.claude/skills/agent-guardrails` і `~/.codex/skills/agent-guardrails`;
- реєструє хуки SessionStart і PreToolUse у `~/.claude/settings.json` та `~/.codex/hooks.json`;
- перед зміною робить резервну копію кожного файлу налаштувань і ніколи не чіпає чужі хуки.

Опції: `--claude`, `--codex`, `--no-hooks` (лише скіл), `--dry-run`, `--uninstall`. Оновлення: `git pull && python3 install.py`.

**Codex:** нові чи змінені хуки Codex запускає лише після того, як ви їх переглянете й довірите. Після встановлення відкрийте Codex і підтвердьте два хуки `agent-guardrails`.

Після цього почніть нову сесію: вже запущені сесії новий скіл не підхоплять.

#### Без хуків

Якщо хуки ставити не хочете, запустіть інсталятор з `--no-hooks` і вставте вміст `skills/agent-guardrails/DIGEST.md` у глобальні інструкції (`~/.claude/CLAUDE.md` або `~/.codex/AGENTS.md`). Тоді правила завантажуються в кожній сесії, але механічно нічого не блокується.

### Що блокує сторож

`hooks/guard.py` перевіряє shell-команди (`Bash` у Claude Code, `exec_command` у Codex) та інструмент `Read` у Claude Code.

| Рівень | Що блокує | Чому |
|--------|-----------|------|
| жорсткий | Читання `.env*` (крім `.env.example`), приватних ключів, `*.pem/*.key/*.p8/*.p12`, файлів облікових даних, `/proc/*/environ`; голий `env`/`printenv`; `docker inspect` без `--format`; `docker compose config` | секрети потрапляють у транскрипт |
| жорсткий | Через `ssh` чи `kubectl exec`: тестові набори, `migrate:fresh/refresh/reset`, `db:wipe`, `db:seed`, `DROP`, `TRUNCATE`, `FLUSHALL` | тести й «свіжі» міграції стирають реальні дані |
| м'який | `git push --force`, `reset --hard`, `checkout .`, `restore .`, `clean -f`, `branch -D`, `stash drop/clear` | знищує роботу, можливо чужу |
| м'який | `git add -A/./--all/-u`, `git commit -a` | комітить чужі зміни |
| м'який | `cat` файлів загальним обсягом понад 40 КБ або 4+ файлів без обмежувального пайпа | вивід обрізається, і частина мовчки лишається непрочитаною |
| м'який (лише Codex) | Python-код не-ASCII через `python3 -` / `-c` | в оболонках агентів не в UTF-8 це падає з `SyntaxError` |

Безпечні форми дозволені. Наприклад: `grep -c KEY .env`, `sed -n 's/=.*//p' .env` (лише назви ключів), `docker inspect -f '{{.State.Status}}' app` і локальний запуск тестів через `docker exec app php artisan test`.

- **М'які блоки** можна свідомо обійти, дописавши до команди `# guardrails:allow <причина>`. Агенту сказано повідомити вам цю причину.
- **Жорсткі блоки** агент обійти не може.
- **Перемикачі:**
  - `AGENT_GUARDRAILS=off` у середовищі агента вимикає все.
  - Файл `.agent-guardrails-off` у проєкті (або в будь-якій батьківській теці) вимикає сторожа для цього дерева.
  - `AGENT_GUARDRAILS_SKIP=secrets,remote,git,read_budget,python_stdin` пропускає окремі перевірки.
  - `AGENT_GUARDRAILS_READ_LIMIT=<байти>` змінює бюджет читання.
- **Відмова на пропуск:** якщо сам сторож зламався, команда проходить. Зламаний сторож не має блокувати вашу сесію.

### Обмеження

- Сторож — евристика, а не пісочниця. Навмисно складена команда його обійде. Він існує, щоб ловити звичні помилки, а не зловмисників.
- 1 145 інцидентів записав Codex і 11 — Claude Code. Правила не прив'язані до агента, але статистика відображає передусім звички Codex.
- Тексти інцидентів не публікуються. Вони описували приватні проєкти, тому тут лише узагальнені категорії й висновки.

### Тести

```bash
python3 -m unittest discover -s tests
```

### Ліцензія

MIT
