# 01 · Guessed Paths and Wrong Working Directory

> The agent reads, edits or calls a file, directory, script or URL that does not exist or lives elsewhere, instead of listing the tree first or taking the path from output it already has. Each failure is cheap (ENOENT, exit code 2, MODULE_NOT_FOUND, 404), but they are frequent, repeat within one session even after the agent promised to stop, and sometimes let a build or test start without the intended edit. **Share:** 204 of 1,156 recorded incidents (17.6%).

## What goes wrong
- **Invented product-code file names or wrong subdirectories** (67) — a source file is opened by an assumed name or at the repo root when it lives in a subfolder (`Network` vs `Networking`, `conftest.py`, a page object, a service class). Often repeated right after a "fixed" search.
- **Invented paths to workflow/QA artifacts** (76) — scenario files, handoffs, receipts, plans, state files, ticket files or memory directories are read or registered under a guessed name or with a missing path segment. A shortened path quoted in a handoff is treated as root-relative.
- **Invented helper scripts and instruction files of a skill or role** (27) — nonexistent helper scripts and role/phase files are invoked by analogy (`agent-budget.mjs`, `verification-ledger.mjs`, `reviewer.md`) while the real names were in the skill's own instructions. The same wrong names recur across sessions.
- **Relative path resolved from the wrong working directory** (24) — an edit, copy, `./gradlew` or lease-tool call runs from one level while the path is written for another: duplicated prefix, `./gradlew` from the repo root (exit 127), one `../` too many or too few. The edit fails with FileNotFoundError, yet the build or test chained after it still runs on old code (13 of these).
- **Invented URL, route or in-environment path** (10) — a health route that does not exist, a static path to a framework's JS asset, a host path used inside a container, an unmounted file, a user-local bin directory, a previous deploy archive at its old location. Result: 404 or a missing directory; once it broke a pre-deploy backup.

## Why it happens
- No file inventory before the first read: the path comes from memory, a similar project, or a shortened mention in a handoff, not from `rg --files` / `git ls-files`.
- Canonical paths of the workflow's own infrastructure (state file, handoffs, receipts, helper scripts) are not recorded in one place, so after a context reset the agent reconstructs them by analogy.
- An edit and a build/test are joined in one shell command without checking the exit code, so the second part runs after the first failed.
- Two roots are mixed in a monorepo (repo root vs a mobile subproject) and relative paths are used while the working directory is not guaranteed between calls.
- "From now on I will use absolute paths" is text in the agent's context, not a check; the same mistake repeats later in the same session.
- Batch-reading many rule files with truncated output makes the agent rebuild known paths from memory.

## What it costs
- Wasted tool calls and a second search for the right path.
- A build or UI test runs against stale code because the edit never applied; a scarce device or build slot is burned and a queue wait is lost.
- Registering a verification result is rejected or skipped because the receipt file is missing, leaving the result unrecorded.
- A false statement to the user (for example "the working copy is gone" when only a path was mistyped).
- Blind spots: a 404 from a guessed URL yields no data; a pre-deploy backup fails on a stale path; a wrong count of `../` in a check script could escape the working copy (caught before running).
- No data loss was recorded; the damage is time, context and a risk of a missed edit.

## How to prevent it
### Pre-tool hook: block reads of nonexistent paths and suggest matches · `hook`
For the Read tool and for Bash commands (`cat`, `head`, `tail`, `sed`, `rg`, `python`, `plutil`) with literal path arguments, check `test -e` on each path before running. If it is missing, do not run the command; return: "Path X does not exist. Closest matches: <output of `fd`/`rg --files` filtered by the same basename, or nearest by edit distance>". This turns a guess into one call with a ready answer.
*Closes:* invented product files, invented workflow paths, invented scripts, invented URLs/paths.

### Paths only from a listing · `rule`
**Rule:**
> Do not read, edit or pass to `rg` any path that did not appear in the output of `ls`, `rg --files --hidden`, or `git ls-files` in this session, or in the task text itself. After a context reset, the first call is a file listing of the workflow state directory, the skill directory and the code root (`rg --files --hidden <dir> | head -200`); take names only from it. A shortened path quoted in a handoff is relative to the run's own directory, not the repo root.

*Closes:* invented product files, workflow paths, scripts.

### Canonical-path registry and shims for frequent inventions · `script`
Provide a command (for example `paths`) or a `paths.json` that prints the real locations: state file, helper scripts, handoff/receipt/ticket directories of the active run, memory index, phase and role file names. Make the skill's instructions point at that output instead of file names in prose. Next to it, place stub scripts for the names agents keep inventing; each exits with code 2 and a message such as "use agent-state.mjs / verification.mjs instead".
*Closes:* invented workflow paths, invented scripts.

### Build/test hook: check working directory and build files · `hook`
Pre-tool hook on Bash: if the command contains `./gradlew`, a lease-wrapped gradle call or `xcodebuild`, and the working directory (or the declared `--workdir`) lacks that file, block with "gradlew is at <`git ls-files '*gradlew'`>; run with an explicit workdir". Pass an explicit workdir to wrappers instead of relying on cwd. Also block when the Xcode project has not been generated yet.
*Closes:* wrong working directory.

### Edit then build only with `set -e` and absolute paths · `rule`
**Rule:**
> In shell and Python edit scripts use absolute paths only (`ROOT=$(git rev-parse --show-toplevel)` first). Never chain an edit and a build/test with `;`: use separate calls, or `set -euo pipefail` / `&&`. After the edit and before the build, run `git diff --stat` and confirm the expected file changed.

*Closes:* wrong working directory (builds started on old code).

### Wrappers for routes and container paths · `script`
Before an HTTP check of a framework route, run `php artisan route:list --path=<fragment>` and take the URL from it; use the framework's script directive or asset helper rather than a hand-written static path. Before `docker exec` or reading inside a container, run `docker exec <c> pwd; ls` and use the container's working directory, not the host path. In a pre-deploy backup script, `test -e` every source and fail before starting any operation.
*Closes:* invented URL/route/environment path.

### Path validator for descriptors and plans · `template/validator`
Run a `validate-paths` script over scenario files, ticket files, agent zones and plans: every path in `inputs`, `zone` or `files` fields must exist or be marked `creates`. Reject invalid descriptors before an executor is admitted, so the check is mechanical rather than accidental.
*Closes:* invented workflow paths, wrong working directory.

### Read rules in bounded pieces · `rule`
**Rule:**
> Read rule files and contracts one file at a time with `head -c 6000`, not as `cat a b c d`. Send large output to a file and read it with `rg` or `sed -n`.

*Closes:* related truncated reads that accompany invented paths.

## Checklist before acting
- [ ] Every path I am about to use appeared in a listing or in the task text this session.
- [ ] After a context reset I ran a fresh file listing before touching workflow files.
- [ ] The path is absolute, or I confirmed the working directory with `pwd` in the same call.
- [ ] The edit command exited 0 and `git diff --stat` shows the expected file before I start a build or test.
- [ ] URLs and routes come from `route:list` / the router source, container paths from `pwd` inside the container.
- [ ] A shortened path from a handoff was resolved against the run directory, not the repo root.
