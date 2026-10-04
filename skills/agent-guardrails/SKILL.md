---
name: agent-guardrails
description: Use in EVERY coding session, before the first tool call and again after a context reset or compaction. Hard-won rules that stop the most frequent coding-agent mistakes - guessed file paths, oversized reads with truncated output, guessed JSON/SQL/API shapes, shell and CLI misuse, broken orchestration protocols, weak tests, unverified "done" claims, secrets in output, and risky actions on shared or production systems. Also use when planning a delegation brief, writing a test, touching a server, or reporting results.
---

# Agent guardrails

Distilled from 1,156 real incidents logged by coding agents (Codex and Claude Code) across mobile, desktop, web and backend projects. Each rule below exists because agents broke it repeatedly. The thirteen categories are ordered by how often they occurred.

Use this file as a working checklist, not as reading material. When a category becomes relevant, open its reference file for the subtypes, root causes and ready-to-paste project rules.

## Before the first action of a session (and after every context reset)

1. **Inventory before reading.** Run `git ls-files` / `rg --files` (scoped, piped to `head`) and take every path from that output or from the task text. Never from memory.
2. **Measure before reading.** `wc -c` / `wc -l` unknown files first. Read rule files and docs one at a time, in ranges.
3. **Know where you are.** `pwd` and `git rev-parse --show-toplevel`. Use absolute paths in anything that edits or builds.
4. **Check who else is here.** `git status --short` and running processes or locks before you build, deploy, restart, or commit in a shared tree or on a server.

## The 13 rules

### 01 · Paths come from listings, never from memory (17.6%)
- A path, file name, route, script name or ID you have not seen in this session's tool output does not exist yet. Find it with `rg --files | rg <name>`, `ls`, `git ls-files`, `route:list`, or the registry that owns it.
- In monorepos, decide which root a relative path is relative to. Prefer `ROOT=$(git rev-parse --show-toplevel)` plus absolute paths.
- Never chain an edit and a build/test with `;`. Use separate calls, or `set -euo pipefail` / `&&`, so a failed edit does not run a stale build.
- One "file not found" means stop and list. Do not try a second guess.
- Details: [references/01-guessed-paths.md](references/01-guessed-paths.md)

### 02 · Read narrowly; truncated output is unread output (16.4%)
- The tool's output limit is a budget for the whole call, not per file. Never `cat` several rule files, docs or sources in one call.
- Size first (`wc -c`), then read by range (`sed -n 'A,Bp'`, `head -c`), one file per call.
- For JSON, registries, receipts and logs, print only named fields (`jq '{a,b}'`, `jq length`, `jq 'keys'`). Never print a whole object, a hash map or a minified one-line file.
- Scope searches (`rg -n PATTERN path -g '*.kt' | head -50`, `git status --short -- path`). Never search `/`, `~`, build directories or `/tmp` recursively.
- If output was truncated, do not count the missing part as read. Re-read the missing range explicitly. Do not promise "next time I'll read narrowly". Change the command now.
- Details: [references/02-read-overflow.md](references/02-read-overflow.md)

### 03 · Product code: handle failure, staleness and real types (12.3%)
- Every read of a file, cache, session or network resource has three outcomes: loaded, empty, **failed**. "Failed" must never be treated as "empty", and must block writes, deletes and overwrites.
- Every async result that writes state carries a request/version/session id. Discard results that arrive late or for a previous session.
- Compare dates as dates, numbers as numbers, enums through one shared mapper. Never compare a string with a datetime.
- Before you rely on platform behavior (media formats, intents, locale formatting, framework lifecycle), run a minimal experiment on the real platform and note the result.
- Build or compile the target after the last edit, before saying "done".
- Details: [references/03-code-logic.md](references/03-code-logic.md)

### 04 · Use tools by their actual interface (11.8%)
- Before the first call of an unfamiliar CLI or subcommand, read `--help` or its parser. Never invent flags, subcommands or argument order.
- Quote globs (`rg -g '*.swift'`, `'**/*.kt'`). Unquoted globs fail in zsh when nothing matches.
- Do not pipe non-ASCII source code (e.g. Cyrillic) into `python3 -` / `python3 -c`. Some agent shells are not UTF-8. Write the script with the file tool, then run it.
- One file, one patch operation. Never Delete+Add or Add+Update the same path in one `apply_patch`.
- Check the environment before running suites: interpreter version, required packages, executable bits, active env vars. Use the project's test runner script if one exists.
- UI drivers: take a fresh snapshot after every screen or keyboard change, and never reuse element references from an old snapshot.
- Details: [references/04-tool-misuse.md](references/04-tool-misuse.md)

### 05 · Inspect the shape before writing code against it (9.8%)
- Before a script reads JSON: print `type()` and the first keys or element type. Lists are not dicts. Fields may be `null`.
- Before SQL: print the schema (`.schema t`, `SHOW COLUMNS`, `\d t`, or the migration). Never guess column names, even in read-only queries.
- Before using a method, property, import or enum value you have not seen in this repo: `rg` for its definition or open the SDK docs.
- Client models follow the server contract file (DTO, OpenAPI, schema), not memory.
- Details: [references/05-guessed-schema.md](references/05-guessed-schema.md)

### 06 · Follow the order of work and stay in scope (6.9%)
- Start a dependent step only on a confirmed readiness signal (build log says success, artifact exists and is newer than the code, container is running). Never start it because "it should be done by now".
- Do not change inputs that a running or pending verification has fixed. Put notes in a separate file.
- Keep leased devices and containers alive for the whole plan. Release by exact id only after the artifacts are collected.
- Edit only files inside your assigned scope. Check `git diff --name-only` against the scope before handing back.
- On a server or in a shared repo: read state first (processes, locks, deploy logs, `git status`), find out who owns what, and never restart, push or deploy over someone else's in-flight work.
- Details: [references/06-process-and-scope.md](references/06-process-and-scope.md)

### 07 · Formal protocols are parsed by machines: copy their schema (6.8%)
- Handoffs, reports, receipts, descriptors and plans are checked by validators. Fill them from the template or generator, never from memory. Exact keywords, exact enums, exact casing.
- Build lists of inputs from `git ls-files` plus explicitly named artifacts. Never use a recursive folder walk or a copied old descriptor.
- Registrations, IDs and receipts are immutable. If one is wrong, create a new one. Do not try to edit or re-register.
- After one rejection: read the helper's usage or validator, fix **all** fields, then retry once.
- Details: [references/07-protocol-violations.md](references/07-protocol-violations.md)

### 08 · A test that cannot fail proves nothing (4.9%)
- Prove every new or changed test can go red: break the code minimally, watch it fail, restore it, and report what you broke.
- Assert only what the public contract guarantees. Cite the contract (file:line) for every expected value. Normalize order when order is not guaranteed. Check counts before `zip`.
- Test preconditions explicitly (`PRECONDITION:` failures), so environment problems are not reported as product failures.
- Wait for a state, not for time: use `waitFor(condition)`, never `sleep`/N×yield.
- Evidence hashes must cover every file the test actually reads.
- Details: [references/08-weak-tests.md](references/08-weak-tests.md)

### 09 · Claims need evidence from this session (4.5%)
- "Done", "works", "released", "deployed" are written only after the check ran, quoting the command and its result.
- Absence of evidence is not evidence of absence. Before saying "X is missing / not configured / not sent", check every place that can define X, and name them.
- A cause is a hypothesis until you have read the code, the log or the screenshot, or run a control experiment. Label it `hypothesis:` until then.
- Copy IDs, versions, timestamps, counts and `file:line` from tool output at the moment of writing. Never type them from memory.
- Details: [references/09-false-claims.md](references/09-false-claims.md)

### 10 · UI: stable selectors, explicit waits, the right screen (2.9%)
- Dump the UI tree before writing a selector. Use testTag / accessibilityIdentifier / data-testid scoped to a container, never text, index or coordinates.
- Confirm the current screen (title, route, activity) before each navigation step.
- Screenshots: set and verify the viewport and URL before capturing. Check 390 px, 768 px and 1280 px for layout changes.
- Review `git diff` of styles: only the selectors named in the task may change.
- A UI test that failed before reaching the checked action means "not verified", not "verified".
- Details: [references/10-ui-defects.md](references/10-ui-defects.md)

### 11 · Delegation: briefs are self-contained and verbatim (2.8%)
- A sub-agent has an empty context. The brief must contain the goal, the exact files, scope, commands, acceptance criteria and output contract.
- Mandatory blocks (rules, report contracts, templates) are pasted **verbatim** from their source file. Never summarize them, paraphrase them, or replace them with "see previous brief".
- Verify every path and key in the brief with `ls` / `rg` before sending.
- Define the write scope after an inventory (code, tests, localization, report directory). Scopes are often immutable after registration.
- Check agent slots and the agent's status before spawning or messaging. Release shared resources only by exact id.
- Details: [references/11-delegation.md](references/11-delegation.md)

### 12 · Map every requirement to evidence before "done" (1.9%)
- List all explicit requirements of the task **and** of the standing project/global rules (version bumps, registries, language, required frameworks, "all/every"). Next to each one, write its evidence (`file:line`, command output, screenshot).
- Verify the claimed property on the artifact itself and on the real client state, not on a convenient substitute.
- Look at the result as the user will see it: no raw API field names, no duplicates, dates in the user's time zone, periods that match their labels.
- Details: [references/12-requirement-gaps.md](references/12-requirement-gaps.md)

### 13 · Secrets never reach the output (1.1%)
- Never `cat` / `grep` / print `.env*`, signing configs, `docker compose config`, `docker inspect`, process argument lists, credential files or server log heads. Filter **before** output: pick named keys or counts (`jq '{build,version}'`, `grep -c`).
- Use an allowlist of fields to show, not a denylist of fields to hide.
- If a secret did reach the output, say so immediately and recommend rotating it. Do not repeat the value.
- Details: [references/13-secrets.md](references/13-secrets.md)

## Before you say "done"

- [ ] Every requirement (task + standing rules) is mapped to evidence from this session.
- [ ] The changed target was built and its tests ran after the last edit. New tests were shown to fail on broken code.
- [ ] `git diff --name-only` contains only files in scope. Nothing was staged with `git add -A` / `-a`.
- [ ] All IDs, numbers, versions and paths in the report were copied from tool output.
- [ ] No secret values appear anywhere in the transcript or the report.
- [ ] Anything not verified is labeled "not verified", with the reason.

## Mechanical enforcement

The installer can register two hooks for Claude Code and Codex:

- `hooks/session_start.py` injects a short digest of these rules at session start, resume and compaction.
- `hooks/guard.py` (PreToolUse) blocks shell commands that print secret files, run destructive database commands over SSH, discard work with destructive git commands, stage everything blindly, or dump several files in one read.
  - Soft blocks can be overridden deliberately by appending `# guardrails:allow <reason>` to the command.
  - Hard blocks (secrets, destructive database commands over SSH) require the user to act.

Rules in text get forgotten. Hooks do not. When a mistake repeats, prefer a hook or a wrapper script over another sentence of instructions.
