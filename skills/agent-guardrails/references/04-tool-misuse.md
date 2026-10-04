# 04 · Tool and CLI misuse

> Agents break their own tool calls before any real work starts: non-ASCII text piped into Python, helper CLIs invoked with guessed flags or outside `PATH`, unquoted globs in zsh, duplicate operations in one patch, stale UI-driver references, and test runs that inherit the wrong environment. Most failures are no-ops (the command never ran) and corrupt nothing, but they repeat in exactly the same form and can be closed by a hook, a wrapper, or a rule. **Share:** 136 of 1,156 recorded incidents (11.8%).

## What goes wrong
- **Python fed non-ASCII text via stdin/heredoc/`-c`** (25) — a script or report containing Cyrillic or other non-ASCII text is piped to `python`; the interpreter rejects the source as non-UTF-8, no file is written, and the agent retries through a file tool or ASCII-escaped JSON. Also: literal `\n` inside `python -c`, and heredocs mangled by a PTY.
- **Helper CLIs called from memory** (32) — the shared-machine lease manager and other in-house scripts are called without an absolute path (command not found), with `--help` treated as a path or build command, with invented flags (`--minutes`, `--platform`), with a resource type where an ID is required, or with `claim` and `release` issued from different, short-lived shells so ownership never matches.
- **Shell and patch syntax** (13) — unquoted `*.swift`, `07-*.md` or regex patterns make zsh answer `no matches found` or expand to a file list; a patch containing Delete + Add on the same path is rejected whole.
- **Invalid orchestration / UI-driver calls** (18) — REPL variable never created after a failed tab lookup, element references reused after the screen changed (clicking the keyboard instead of a button, corrupting a field), lost PTY session IDs, malformed JS/JSON (a string where an array is required), out-of-range parameters (`limit` above the maximum, path without a leading slash).
- **Tests and builds with implicit environment** (15) — PHPUnit in Docker without `APP_ENV=testing`/`SESSION_DRIVER=array`, with inherited queue/search drivers, no `.env`/`APP_KEY`; iOS builds with `CODE_SIGNING_ALLOWED=NO` (Keychain unusable), no `DEVELOPMENT_TEAM`, `xctestrun` without `TESTROOT`; an Android source set that declares one directory.
- **Unchecked runtime** (23) — system Python 3.9 instead of 3.11+, missing `hashlib.file_digest` or `bs4`, script without `+x`, `rename` across disks, `docker cp` into a read-only container, PHP out of memory, store API called without `Accept: application/a-gzip`, `urllib` blocked by a CDN, a reserved SQL word (`rows`) used as an alias, two "completed" releases on a store track.
- **Other local edit/script slips** (10) — wrong PHPUnit `TestWith`, an `@php` block in Blade, a global replace that hit a function name, a text edit that deleted classes, reading a non-existent XML/JSON, `git add` of an ignored file.

## Why it happens
- The command is composed from an assumed syntax instead of from the tool's actual help or schema.
- Python-via-stdin is the default way to write text, although the agent runtime does not pass it as UTF-8; the "add encoding / escape to ASCII" fix is applied after the fact every time.
- The agent shell has no configured `PATH` and no persistent TTY, so helper CLIs and lease ownership break between calls.
- Implicit environment variables (`APP_ENV`, session/queue/search drivers, iOS signing) override `phpunit.xml` and defaults, and each test command is hand-assembled differently.
- Tool state (REPL variables, element references, PTY session IDs) is assumed to survive an error or a screen change.
- Nothing validates a command before it runs, so patch conflicts, unquoted globs and missing files surface only at execution.

## What it costs
- No-op calls: builds, checks and report writes repeated, often dozens of times.
- False failures: hundreds of PHPUnit failures and false search-test failures from a wrong environment; half of a test suite failing for lack of `APP_KEY` plus a very large log dumped into context.
- Invalid E2E results on an unsigned iOS build (no Keychain): repeated registration, throttling, corrupted test input (a field value silently multiplied).
- Orphaned device/Docker leases that must be audited; an emulator without a lease vanishing with its shell.
- A server stopped without a backup after a SQLite WAL open error; storage classes temporarily deleted by a text edit.
- Lost time and context from truncated or oversized output and extra terminals/tabs left open; a store publish rejected with HTTP 400.

## How to prevent it
### Block non-ASCII Python via stdin · `hook`
A PreToolUse hook on shell commands: if the command starts with `python`/`python3` and uses `<<`, `-` as stdin, or `-c`, and the text matches non-ASCII letters (for example `[^\x00-\x7F]`), block it with: "Write reports/translations with the file-edit tool; run Python only from a script file or with ASCII-only source."
**Rule:**
> Do not pass non-ASCII text to Python via stdin, heredoc or `-c`. Write text and reports with the file-edit tool; write JSON metadata ASCII-escaped (`ensure_ascii=True`).

*Closes:* Python via stdin.

### Make helper CLIs self-describing and reachable from any shell · `script`
Symlink the helper into a directory on the non-interactive `PATH` (or export it from `~/.zshenv`, which non-interactive shells read). In the helper: `-h/--help` works on every subcommand (exit 0, prints usage); unknown flags or `--help` used as a path exit 2 with a hint ("use `--for N`; project path is positional"); alias common guesses (`--minutes` to `--for`); reject `release ios|android|docker` with "selector must be `all`, an ID, a name, a UDID or an emulator port"; `--help` on `build` must never enqueue a job.
*Closes:* helper CLIs.

### Keep leases in one persistent shell · `process`
**Rule:**
> Run lease `claim` and `release` only from one persistent interactive PTY session opened once, whose session ID is recorded. Release with the exact ID or UDID from `status`.

The wrapper refuses `claim` when stdin is not a TTY or the parent process is short-lived (exit 3 with a message), and `status` prints a ready-to-paste `release <ID>` for the caller's own leases.
*Closes:* leases from the wrong shell.

### One test-runner script with a fixed environment · `script`
A `test-backend.sh` for Docker exports `APP_ENV=testing`, `SESSION_DRIVER=array`, `QUEUE_CONNECTION=sync`, `SCOUT_DRIVER=null`, an explicit test database, and checks for `.env` and `APP_KEY` before PHPUnit (stop on failure; do not chain with `&&` in a way that still runs tests). Output goes to a file and is read with `tail -n 40`. An `ios-test.sh` does the same: `CODE_SIGNING_ALLOWED=YES` for the simulator, `DEVELOPMENT_TEAM` from private config, required phase variables, correct `TESTROOT` for `xctestrun`.
**Rule:**
> Run tests only through these scripts; never assemble the command by hand.

*Closes:* tests/builds with wrong environment.

### Pre-validate patches and shell commands · `hook`
A validator before `apply_patch`: if one path appears in two operations (Delete+Add, Add+Update), reply "replace a file with one Update File operation, or do the delete in a separate patch". A shell hook: for zsh commands with unquoted `*`, `?`, `[` in `rg`/`grep`/`ls`/`cat`, suggest quotes or `rg --files -g '<glob>'`; add `setopt NO_NOMATCH` to the non-interactive zsh env.
**Rule:**
> Always quote search patterns; list files with `rg --files` first.

*Closes:* zsh globs, double operations in a patch.

### REPL, UI-driver and PTY discipline · `rule`
**Rule:**
> In a JS REPL, create the tab and bind the variable in one expression and branch on the lookup result; after an error do not assume the variable exists. In a UI driver, take a fresh snapshot after every screen or keyboard change and never click an element reference from an old one; check the button is not covered by the keyboard; re-read field values after typing. Keep the full terminal result with its session ID; never poll a PTY you did not open.

*Closes:* invalid orchestration/UI-driver calls.

### Environment preflight · `script`
A `check-env.sh` prints `python3 --version` (require >=3.11 or use the project `.venv/bin/python`), checks required packages, `ffmpeg`, `+x` bits, and that every file path passed downstream exists.
**Rule:**
> Never use the system Python 3.9; use the project venv or a pinned Homebrew Python. Check a JSON/XML file exists before reading it. Use `curl` for HTTP uploads; send `Accept: application/a-gzip` to store-report endpoints.

*Closes:* unchecked runtime.

### Argument schema table and dry-run for helper CLIs · `template/validator`
In AGENTS.md add a table "subcommand -> required arguments -> example" for each helper (evidence is an array; progress takes a remaining-count argument; `ask` takes a positional argument before options). Add a `--check`/`--dry-run` mode to each script that validates arguments with no side effects.
*Closes:* helper CLIs; invalid calls.

## Checklist before acting
- [ ] Does this command need non-ASCII text on stdin? Use a file tool instead.
- [ ] Is the helper called by absolute path, with flags confirmed from `--help` or the schema table?
- [ ] Are all globs and regexes quoted; does the patch touch each path once?
- [ ] Is the UI/REPL state fresh (new snapshot, variable confirmed to exist)?
- [ ] Do tests run through the fixed-environment script, with the interpreter version and required files checked first?
- [ ] Is the lease being claimed from a persistent shell and released by exact ID?
