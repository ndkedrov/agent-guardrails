# 06 · Process order and scope violations

> Agents perform correct actions at the wrong moment or in the wrong place: starting a step before its dependency is ready, losing a device/Docker lease, changing pinned inputs before a result is recorded, leaving the allowed scope, or acting in a shared or production environment without checking whose it is. Damage was usually limited to a wasted run because safeguards (lease reaper, input-fingerprint log, checkout) held, but a few cases touched production or another party's deploy. **Share:** 80 of 1,156 recorded incidents (6.9%).

## What goes wrong
- **Next step started before the previous one finished** (17) — a test, copy, file read or push runs before the build, file write, container start or earlier suite completes. Result: file-not-found, stale APK/code, zero tests, a push with no new commit.
- **Lease lost through lifecycle** (11) — a lease issued from a short-lived shell is judged orphaned by the reaper and its containers are stopped; or a lease is released/expired while a check is still running (copying XML, UI clicks, a repeated logcat). A local server started inside a worker's temporary context dies mid-write.
- **Wrongly prepared test environment or stale artifact** (13) — Docker brought up from the server compose file instead of the local one, missing directories/mount points/Xcode project, an already-used subnet, an old Debug build or modified temporary model file; stand data that violates the app's policy.
- **Pinned inputs changed before the result was recorded** (6) — a test file, descriptor, spec or build number edited before the verification log recorded the result, so the fingerprint changed and the PASS/FAIL entry was rejected; the check had to be cancelled and repeated.
- **Out of scope or role** (7) — reading files outside the allowed zone, a repository-wide replace instead of the sources folder, widening a resubmission to extend a test harness, overwriting tracked state from earlier work, an orchestrator reading product code.
- **Acting in a shared/live environment without checking context or lease rules** (14) — restarting a container during someone else's deploy, pushing a side branch to a repo whose deployer builds any branch, a `git pull` that rolled back a submodule, building a production image without an isolated test, two controllers on one simulator, git as root, commands without the lease wrapper, edits before the preflight check.
- **Repeated, redundant or unauthorized work** (12) — re-uploading an already accepted bundle (403), creating an already existing localization (409), re-running a parser (duplicates), a repeated helper, asking for an unnecessary edit permission, a needless question to the user, many short status polls instead of one wait, a command over the 5-minute limit.

## Why it happens
- A step starts by plan order, not on a confirmed readiness signal (build succeeded, file exists, container healthy, receipt written); nobody checks the signal, so the "next command" fires immediately.
- The lease manager identifies the owner by process; an agent calling `claim` in a short-lived shell makes the reaper see an orphan once the shell exits. The agent did not know this mechanism.
- A lease is issued for an expected duration but the end of the check is never compared with the time left, and `release` is done "when it feels done", not after the artifacts are collected.
- Resource identifiers and paths are assumed: a name instead of a UDID, relative paths, `/tmp` instead of its real target, a subnet picked without inspecting networks, the server compose file instead of the local one.
- The verification log fingerprints inputs, but agent and coordinator share no rule "do not touch inputs until the result is recorded".
- The allowed zone and foreign context are described only as brief text and not checked before acting: unscoped reads, "whole folder" patterns, pushing a branch without reading the deployer rules, restarting without checking who owns the running deploy.
- Operations are assumed idempotent or not yet done: repeated upload, parser, helper, or creating a localization the API already created.

## What it costs
- Lost test and UI runs that had to be repeated: zero tests, an old build, truncated access JSON, a six-minute command with no result.
- Containers stopped by the reaper before tests began; leases had to be moved into a persistent PTY session.
- The verification log rejected a result because of a changed fingerprint; checks were cancelled and counted as "cancelled", not PASS/FAIL.
- A foreign production deploy interrupted: a stuck deploy lock and HEAD on an older commit, cleaned up only by removing the lock as the web user.
- A failed-deploy alert to the owner after a side-branch push; production avoided switching only through an unrelated untracked file.
- A production image with new CAD-library versions broke import for every part of a product; the previous image was restored.
- Duplicate entries in a fix-conditions log, progress temporarily removed from a dashboard, archived code snapshots touched and rolled back by checkout.
- Local test-stack configuration passwords printed twice into tool output.
- Needless user prompts and delayed report uploads; a user entered an expired code and got locked out.

## How to prevent it
### `ready` wrapper before every dependent step · `script`
A `ready <type> <target>` script with a timeout up to 5 minutes and a non-zero exit: `file <path>` (exists, size stable, JSON valid), `build <log>` (contains `BUILD SUCCESSFUL`/`BUILD SUCCEEDED` and the artifact's mtime is newer than the last code change), `container <name>` (running + healthcheck), `receipt <id>`.
**Rule:**
> A step that reads a file, APK or container created by a previous step starts with `ready ...`. Never launch it as the "next command" beside the dependency's start.

*Closes:* next step before the previous finished; stale artifact.

### Lease only from a persistent PTY, check before use · `rule`
**Rule:**
> Run lease `claim` only in a persistent interactive PTY session that lives until `release`; never from a one-shot command. Before every UI click, Docker command and `release`, run `status` and confirm the lease is alive with more time left than the planned step. Release only after the artifacts (XML, logs, screenshots) are copied and their existence is verified.

Add a `claim-safe` wrapper that refuses when the parent process is not a long-lived PTY.
*Closes:* lease lost through lifecycle.

### Hook on claim: assigned resource and pre-start checks · `hook`
PreToolUse hook for `docker`/`xcodebuild`/`adb`/`maestro` commands. Block when (a) no lease exists for this project, (b) the UDID in the command differs from the one issued, (c) `docker compose` runs without an explicit local `-f` file, (d) the path is relative or points at a symlinked temp directory instead of its real target. The block message names what to fix. Also block the next command if the `claim` exit code was not checked (use `claim && bootstrap`, not separate lines that run regardless).
*Closes:* wrongly prepared environment; leases; actions without the wrapper.

### Freeze inputs until the result is recorded · `process`
**Rule:**
> After starting a check with pinned inputs, do not change manifest files (code, descriptors, spec, build number) until the coordinator confirms the receipt exists. Write notes and fixes into a separate file outside the manifest.

In the recorder, run `chmod a-w` on manifest files before the check starts and lift it only after the receipt is written.
*Closes:* changed pinned inputs.

### Explicit scope allowlist plus a diff check · `hook`
The subagent brief names its zone in a `scope.txt` of paths/globs. A PreToolUse hook on Read/Edit/Bash (`sed -i`, `python -i`) blocks paths outside it; bulk-replace scripts take a directory from `scope.txt`, never `.`. Before handing back, compare `git diff --name-only` with `scope.txt`; any extra file returns the task for rework.
**Rule:**
> Run bulk replacements only with `--dry-run` and only inside the sources folder.

*Closes:* out of scope or role.

### Check foreign context before acting on a shared or live environment · `rule`
**Rule:**
> Before restart/push/pull/deploy on a server or in a repo with a deployer: (1) run the shared-machine preflight check before the first edit; (2) on the server only read `ps`, the deploy lock and the deploy log, and find out whose process it is; do not restart while the lock and process are foreign; (3) before pushing a new branch read the webhook/deployer rules; pushing to an auto-deploy branch needs confirmation; (4) run git as the web-server user only; (5) before rebuilding a production image pass an isolated artifact test.

A hook blocks `git push` to a non-main branch in a repo marked as auto-deploy, and `docker restart` without a prior read of the lock.
*Closes:* actions in shared or live environments.

### Idempotency and a done-steps log · `template/validator`
Wrap API operations (store bundle upload, store localizations, report parsers) so they first read current state (GET: which version code is already accepted, which localization exists) and only then POST/PATCH. Parsers log the hash of processed inputs and refuse the same input twice. For waiting: use one wait with a timeout, not a series of short polls; stop any command that exceeds 5 minutes.
*Closes:* repeated or redundant work.

### Isolate shared simulators and test stands · `process`
Before handing a shared resource (a hardware simulator, a local server, a build in DerivedData) to the next platform, stop your own app and confirm it with a command. Use a separate build directory and separate test-data files per run. Start long-lived servers as detached processes with a recorded PID, never from the worker's context.
*Closes:* wrong environment; lifecycle; shared resources.

## Checklist before acting
- [ ] Did a readiness check (`ready file|build|container|receipt`) pass for every input this step needs?
- [ ] Does `status` show my lease alive with more time left than this step needs, in a persistent shell?
- [ ] Are the pinned inputs untouched since the check started (no edits before the receipt)?
- [ ] Is every file and command inside the scope list (`git diff --name-only` matches)?
- [ ] On a shared or live environment: whose process, lock and deploy is this, and did I only read first?
- [ ] Has this operation already happened (GET current state before upload, create or parse)?
