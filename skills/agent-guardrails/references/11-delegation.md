# 11 · Delegation brief mistakes

> An orchestrator often wrote the brief for a sub-agent from memory or in its own words: it shortened verbatim contracts, paraphrased templates, gave inexact paths, registered a write zone that was too narrow, or handed over permissions late. The common outcome is the same: the executor stopped, waited, or returned a report in the wrong format, and a clarification or a fresh context was needed. Twice, a mistake also released another session's device lease. **Share:** 32 of 1,156 recorded incidents (2.8%).

## What goes wrong
- **Verbatim block or template shortened, paraphrased, or replaced by a link** (10) — instead of copying a shared-resource block, a report contract, or a handoff template word for word, the orchestrator gave a pointer, a short version, or its own wording, or changed individual words while copying.
- **Inexact path, file name, key, or type in the brief** (6) — a shortened or invented file name, a path without the application directory, a wrong config key, a wrong claim about which file declares a type, or "do not use git" without "only for changes". The executor searches for something that does not exist, stops, and asks.
- **Write zone, permissions, or sandbox set incorrectly** (5) — the initial write scope was registered too narrowly (only the first report file, no localization files, an unverified path) or old contexts with a restricted sandbox were resumed. The guard does not allow widening the zone of an existing context, so a new context is required.
- **Permissions, run ID, or launch command passed late or not at all** (4) — the approvals for checks were prepared but the ID, go-ahead, or command never reached the executor, or the agent was not registered under its actual ID. The executor waited, exhausted its context, and finished without running checks.
- **Wrong instruction or wrong requirement mapping in a delegation** (4) — the executor was told something that contradicts a rule or contract (a ban on a release upload, an over-strict `source` condition), model inheritance was pinned wrongly in a contract, or requirements were mapped to unrelated tickets.
- **Shared-resource and agent-slot coordination** (3) — an agent released a lease by a package name shared across two platforms and removed a neighbour's iOS lease; launching a fifth agent hit the slot limit; a message sent to an interrupted agent did not resume it.

## Why it happens
- The brief is composed from memory instead of being copied mechanically from a source file, so paraphrases, shortenings, and accidental word swaps appear.
- The orchestrator assumes the sub-agent sees earlier conversation or inherits context. It does not: its context is empty.
- Paths, keys, and the place where a type is declared are stated without checking the file system before the brief is sent.
- The write zone is registered before the files actually needed (localization, report directory, platform path) are inventoried; once registered, the zone is immutable.
- Granting an approval is a separate step from handing it to the executor, with no mechanical link between them.
- Resources and agents are released or started by an ambiguous identifier (a package name shared by two platforms) or without checking agent status and free slots.

## What it costs
- Executors stopped to ask instead of working: they could not read a diff, searched for a non-existent file, or could not find an artifact path.
- Reviewer reports failed the machine parser and needed reformatting.
- Executors ended their context without the planned checks (desktop runs, unit/UI runs on a mobile platform), requiring a new lease and a new executor.
- Several child contexts hung on escalation prompts and never ran their checks; one agent never received its task because it was in an interrupted state.
- A wrong instruction delayed a release upload; a wrong gate rejected supported physical devices.
- Another session's device lease was removed (its test happened to have already finished).
- New contexts had to be created from scratch because the zone is immutable, and a call counter was temporarily understated.

## How to prevent it
### Assemble the brief with a script from source files · `script`
A `build_brief` script takes the task template and inserts verbatim the shared-resource brief block, the reviewer report contract (verdict line plus required sections), and the handoff template. The orchestrator writes only the variable part: goal, zone, paths. Refuse to send an Agent or send-message call whose brief lacks the begin/end markers of the inserted blocks.
*Closes:* verbatim block shortened, paraphrased, or replaced by a link; reviewer brief without the required format.

### PreToolUse hook on sub-agent launch: verify inserted blocks · `hook`
Before an Agent call the hook checks that the prompt contains the full text of the required brief block (compare a hash of the substring) and none of the phrases "see the previous brief", "as in the earlier assignment", "by analogy". For a reviewer it also looks for the `VERDICT:` line and every section of the contract. If anything is missing, block with a message naming exactly what is missing.
*Closes:* verbatim block shortened; reviewer brief without required format.

### Verify paths and keys in the brief before sending · `hook`
Extract every path-like token from the prompt (contains `/` and an extension) and check that it exists from the project root; block on a missing path. For config keys, obtain the list of key names with a command (names only, no values) and paste it into the brief instead of writing it from memory.
*Closes:* inexact path, file name, key, or type.

### Write-zone checklist before registering an executor · `rule`
> **Rule:** An agent's write zone is immutable after registration. Before registering, list: (1) code files, (2) tests, (3) localization files for new messages, (4) the report directory (not a single file), (5) paths verified with `ls`. Register the zone as a directory, not as the first file. Start a new executor with a full sandbox; do not resume an old context.

*Closes:* write zone, permissions, or sandbox set incorrectly.

### Grant and hand-off are one action · `script`
A `grant_and_send` wrapper creates the approval (run ID / go-ahead) and immediately sends it to the executor together with the exact launch command; exit without delivery confirmation is an error. Register the agent at the moment its actual ID is received. Verify a handoff file with `ls` before referring to it.
*Closes:* permissions, run ID, or launch command passed late.

### Release a lease only by serial or UDID · `hook`
A hook on the lease-release command rejects a call whose argument is a package or bundle name and accepts only the exact emulator serial or simulator UDID that the agent owns (cross-checked against the lease manager's status output).
> **Rule:** Release only by the serial/UDID of your own lease; a package name is shared by both platforms.

*Closes:* shared-resource coordination.

### Check status and slots before messaging or launching an agent · `rule`
> **Rule:** Before send-message, check the agent's status; if it is interrupted, use a follow-up task instead. Before launching a new agent, count occupied slots (maximum four); if full, queue the task instead of calling Agent. In an orchestration workflow, set `model` explicitly on every call that creates a new context.

*Closes:* shared-resource coordination; wrong instruction in delegation.

### Reconcile the brief with the manifest and contract · `process`
Before sending, read the imported rule the brief cites (for example the release-upload rule) and compare each prohibition or requirement with the contract file (for example the allowed `source` values). A script checks the requirement-to-ticket mapping: each manifest line must map to exactly one ticket with a matching domain.
*Closes:* wrong instruction or wrong requirement mapping.

## Checklist before acting
- [ ] Every mandatory block is pasted verbatim from its source file (not linked, not summarized).
- [ ] Every path in the brief exists (`ls` / `test -f`); config keys come from a command, not memory.
- [ ] The write zone covers code, tests, localization, and the report directory, registered as directories.
- [ ] The approval/run ID is delivered to the executor in the same step it is created.
- [ ] Any lease I release is identified by serial/UDID and is mine according to the status output.
- [ ] Agent status and free slots are checked before messaging or launching.
