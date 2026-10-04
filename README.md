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
  hooks/guard.py           PreToolUse hook: blocks secret leaks and destructive commands (see below)
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

Options: `--claude`, `--codex`, `--no-hooks` (skill only), `--enable git_stage_all,read_budget`, `--dry-run`, `--uninstall`. To update, run `git pull && python3 install.py`.

**Codex:** Codex runs new or changed hooks only after you review and trust them. Open Codex after installing and approve the two `agent-guardrails` hooks.

Start a new session afterwards; running sessions do not pick up a new skill.

#### Without hooks

If you prefer not to install hooks, use `--no-hooks` and paste the contents of `skills/agent-guardrails/DIGEST.md` into your global instructions (`~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`). The rules then load every session; nothing is enforced mechanically.

### What the guard blocks

`hooks/guard.py` inspects shell commands (`Bash`; Codex reports its shell commands under the same name) and Claude Code's `Read` tool. It is deliberately narrow: it targets what destroys data or leaks secrets, not style.

**On by default**

| Rule | Blocks | Level |
|------|--------|-------|
| `secrets` | Printing secret values: `cat .env`, `grep TOKEN .env`, `grep -n . .env`, private keys, `*.pem/*.key/*.p8/*.p12`, credential files, `/proc/*/environ`, bare `env`/`printenv`, `docker inspect` without `--format`, `docker compose config` | guarded |
| `remote_db` | Over `ssh` / `kubectl exec`: test suites, `migrate:fresh/refresh/reset`, `db:wipe`, `db:seed` without `--class`, `DROP`, SQL `TRUNCATE`, `FLUSHALL` | hard |
| `git_destructive` | `git push --force`, `reset --hard`, `checkout .`, `restore .`, `clean -f` | soft |

**Opt-in** (`python3 install.py --enable git_stage_all,read_budget`)

| Rule | Blocks | Level |
|------|--------|-------|
| `git_stage_all` | `git add -A/./--all/-u`, `git commit -a`. Useful when several agents share one working tree | soft |
| `read_budget` | `cat` of more than 40 KB without a limiting pipe | soft |

**Not blocked**, because it is routine:
- `git add -A`, `git commit -a`, `git branch -D`, `git stash drop`, `git restore --staged .`, `--force-with-lease`;
- `cp .env.example .env`, `sed -i … .env`, `grep APP_URL .env` (named non-secret keys), `grep -c` / `-l` / `--files`, key-name listings (`sed -n 's/=.*//p' .env`);
- tests run locally (`docker exec app php artisan test`), and `ssh … migrate --force` / `db:seed --class=…`.

**Levels**
- **soft**: the agent may re-run the command with `# guardrails:allow <reason>` when the action is really intended.
- **guarded**: the block is lifted only by `# guardrails:allow user asked: "<the user's words>"`.
- **hard**: only the user can run it.

**The user's explicit request wins.** The skill tells agents that the rules limit their *own initiative*. If you explicitly ask for something a rule discourages ("show me the whole .env", "force-push it"), the agent does it. If the guard blocks the command, the agent re-runs it with `# guardrails:allow user asked: "<your words>"` without asking you again. Agents are told never to add this marker on their own. The only thing an agent cannot unlock is a hard block: it shows you the command and you run it yourself.

**How much it gets in the way.** Replaying three weeks of real sessions on the author's machine through the default rules:

| Agent | Shell commands | Would be blocked | Mostly |
|-------|---------------:|-----------------:|--------|
| Claude Code | 94,110 | 194 (0.21%) | rule hits: 165 secret prints (`grep KEY/TOKEN/PASSWORD .env`, `cat .env`), 32 destructive git, 6 remote DB (a few commands trip two rules) |
| Codex | 36,686 | 8 (0.02%) | secret prints |

The two opt-in rules were measured the same way. `git_stage_all` would block 1 in 144 Claude commands, and `read_budget` 1 in 43 Codex commands, mostly legitimate skill reading. That is too disruptive to enable by default.

**Switches**
- `AGENT_GUARDRAILS=off` in the agent's environment disables everything.
- A file named `.agent-guardrails-off` in a project (or any parent directory) disables it for that tree.
- `AGENT_GUARDRAILS_SKIP=secrets,remote_db,git_destructive` skips individual rules. `AGENT_GUARDRAILS_ENABLE=git_stage_all,read_budget` turns on the opt-in ones.
- `AGENT_GUARDRAILS_READ_LIMIT=<bytes>` changes the read budget.
- **Fail-open:** if the guard itself fails, the command goes through.

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
  hooks/guard.py           хук PreToolUse: блокує витоки секретів і руйнівні команди (див. нижче)
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

Опції: `--claude`, `--codex`, `--no-hooks` (лише скіл), `--enable git_stage_all,read_budget`, `--dry-run`, `--uninstall`. Оновлення: `git pull && python3 install.py`.

**Codex:** нові чи змінені хуки Codex запускає лише після того, як ви їх переглянете й довірите. Після встановлення відкрийте Codex і підтвердьте два хуки `agent-guardrails`.

Після цього почніть нову сесію: вже запущені сесії новий скіл не підхоплять.

#### Без хуків

Якщо хуки ставити не хочете, запустіть інсталятор з `--no-hooks` і вставте вміст `skills/agent-guardrails/DIGEST.md` у глобальні інструкції (`~/.claude/CLAUDE.md` або `~/.codex/AGENTS.md`). Тоді правила завантажуються в кожній сесії, але механічно нічого не блокується.

### Що блокує сторож

`hooks/guard.py` перевіряє shell-команди (`Bash`; Codex передає свої shell-команди під тією самою назвою) та інструмент `Read` у Claude Code. Він навмисно вузький: ловить те, що знищує дані чи виносить секрети, а не стиль.

**Увімкнено за замовчуванням**

| Правило | Що блокує | Рівень |
|---------|-----------|--------|
| `secrets` | Вивід значень секретів: `cat .env`, `grep TOKEN .env`, `grep -n . .env`, приватні ключі, `*.pem/*.key/*.p8/*.p12`, файли облікових даних, `/proc/*/environ`, голий `env`/`printenv`, `docker inspect` без `--format`, `docker compose config` | захищений |
| `remote_db` | Через `ssh` / `kubectl exec`: тестові набори, `migrate:fresh/refresh/reset`, `db:wipe`, `db:seed` без `--class`, `DROP`, SQL `TRUNCATE`, `FLUSHALL` | жорсткий |
| `git_destructive` | `git push --force`, `reset --hard`, `checkout .`, `restore .`, `clean -f` | м'який |

**Вмикаються окремо** (`python3 install.py --enable git_stage_all,read_budget`)

| Правило | Що блокує | Рівень |
|---------|-----------|--------|
| `git_stage_all` | `git add -A/./--all/-u`, `git commit -a`. Корисно, коли кілька агентів працюють в одному робочому дереві | м'який |
| `read_budget` | `cat` понад 40 КБ без обмежувального пайпа | м'який |

**Не блокується**, бо це рутина:
- `git add -A`, `git commit -a`, `git branch -D`, `git stash drop`, `git restore --staged .`, `--force-with-lease`;
- `cp .env.example .env`, `sed -i … .env`, `grep APP_URL .env` (названі несекретні ключі), `grep -c` / `-l` / `--files`, перелік назв ключів (`sed -n 's/=.*//p' .env`);
- локальні тести (`docker exec app php artisan test`), а також `ssh … migrate --force` / `db:seed --class=…`.

**Рівні**
- **м'який**: агент може повторити команду з `# guardrails:allow <причина>`, якщо дія справді задумана.
- **захищений**: блок знімає лише `# guardrails:allow user asked: "<слова користувача>"`.
- **жорсткий**: виконати команду може тільки сам користувач.

**Явне прохання користувача важливіше за правила.** Скіл прямо каже агентам, що правила обмежують їхню *власну ініціативу*. Якщо ви явно просите те, від чого правило застерігає («покажи весь .env», «зроби force-push»), агент це робить. Якщо сторож блокує команду, агент повторює її з `# guardrails:allow user asked: "<ваші слова>"`, не перепитуючи вас. Ставити цю позначку з власної ініціативи агентам заборонено. Обійти агент не може лише жорсткий блок: тоді він показує вам команду, і ви запускаєте її самі.

**Наскільки це заважає.** Три тижні реальних сесій на машині автора, програні через правила за замовчуванням:

| Агент | Shell-команд | Було б заблоковано | Здебільшого |
|-------|-------------:|-------------------:|-------------|
| Claude Code | 94 110 | 194 (0,21%) | спрацювання: 165 виводів секретів (`grep KEY/TOKEN/PASSWORD .env`, `cat .env`), 32 руйнівні git-команди, 6 віддалених БД (кілька команд зачепили два правила) |
| Codex | 36 686 | 8 (0,02%) | виводи секретів |

Два правила, що вмикаються окремо, заміряно так само. `git_stage_all` блокував би кожну 144-ту команду Claude, а `read_budget` — кожну 43-тю команду Codex, переважно законне читання скілів. Для увімкнення за замовчуванням це надто заважає.

**Перемикачі**
- `AGENT_GUARDRAILS=off` у середовищі агента вимикає все.
- Файл `.agent-guardrails-off` у проєкті (або в будь-якій батьківській теці) вимикає сторожа для цього дерева.
- `AGENT_GUARDRAILS_SKIP=secrets,remote_db,git_destructive` вимикає окремі правила. `AGENT_GUARDRAILS_ENABLE=git_stage_all,read_budget` вмикає додаткові.
- `AGENT_GUARDRAILS_READ_LIMIT=<байти>` змінює бюджет читання.
- **Відмова на пропуск:** якщо сам сторож зламався, команда проходить.

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
