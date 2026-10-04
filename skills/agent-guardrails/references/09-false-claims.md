# 09 · Unverified and false claims

> Agents state as fact what they never checked against a source: a state ("deployed", "PASS", "released"), an absence ("not in .env", "not submitted"), a cause, a number, a time, or a name. Almost always someone else caught it (coordinator, reviewer, owner, next agent) or a pre-write check did; the cost is extra iterations and false reports rather than data loss. Hand-copied numbers, times, and identifiers dominate: about half of the incidents involve manually typed values and names. **Share:** 52 of 1,156 recorded incidents (4.5%).

## What goes wrong
- **"Done / working / released" without checking actual state** (9) — change declared deployed, build PASS, lease released, backend ready, or a transition added, while the check covered a previous state, did not finish, or never ran (code not wired into HEAD, command still waiting for a slot, receipt written before the result was read).
- **Categorical "absent / not sent / required" from one source** (8) — absence or a requirement asserted after looking in one place: an env file instead of the admin integrations store, an API response without the review-queue state, a 403 blamed on the IP when the cause was the User-Agent, a truncated search excerpt instead of an exact read, an unverified live data-deletion page, a field assumed mandatory for every API.
- **Hypothesis about cause presented as established** (9) — cause named before verification: from a compiler message, from a selector without looking at the screenshot, without reading the handler, from an assumption about who changed a setting. Reading the code or a control experiment later refuted it.
- **Hand-typed numbers, versions, timestamps, line numbers not checked against the source** (14) — values copied from memory or context instead of the registry, clock, manifest, `php -v`, a hash, or a numbered file: call counters (79 vs 84), a clock time off by minutes, a library version, a language runtime minor version, 12 distinct snapshots vs 11, 8 files vs 7, 5 tests vs 16, line numbers.
- **Wrong name, ID, or path when transferring into a description or record** (12) — the wrong object written: a predicted ID instead of the returned one, the wrong manifest row, the wrong type name, a stale manifest link, a truncated UUID, an inherited run name, a path with a stray space, the wrong app, the wrong data origin.

## Why it happens
- Values (IDs, numbers, times, versions, names) are retyped from memory, project context, or the previous message instead of read from a machine source at write time (registry, clock, runtime version command, API response, hash, manifest).
- A check uses the nearest available source and its result is generalized: one file, one output line, a "nothing released" reply, two passing logos.
- Status is written before the action completes: receipt PASS, `released=true`, `review_submitted=false`, a checkpoint set before the result is read, and the record is not re-read afterward.
- Absence of evidence is treated as evidence of absence ("not in .env", "not sent", "a new release is needed") without an UNVERIFIED label.
- A cause is voiced before a control experiment or inspection of the artifact (screenshot, handler code, higher-precision export).
- Statements about other agents' work are passed along without confirmation from the author.

## What it costs
- False reports to the owner or coordinator: a deleted HTML report claiming a batch ran when no record was queued, a wrong test-coverage caveat, a wrong link table.
- Extra iterations and diagnostics driven by a wrong hypothesis, checks on the wrong app, a rejected result write, a delayed registration caused by a path with a space.
- The user got a build error where the agent had reported it working; the user had to supply the fix.
- Wrong statuses in receipts and logs: a lease still active, a PASS receipt on a stale build, an event with a future timestamp.
- No data or production damage was recorded in many of these cases; the harm is wasted time and eroded trust in reports.

## How to prevent it
### Machine counters and timestamps instead of hand-typed ones · `script`
A `checkpoint` script fills call totals from the registry, the time from `date` (in the user's local time zone), the unique-file count from `sha256sum | sort -u | wc -l`, and versions from `php -v` / `node -v` / the package manifest. In the checkpoint template these fields hold placeholders such as `{{from_registry}}`; the validator rejects a manually typed number.
*Closes:* hand-typed numbers, versions, timestamps.

### Receipt validator: status only after the action · `template/validator`
Reject `PASS`, `released=true`, `review_submitted=false` without an `evidence` field (command + exit code + hash or output, captured AFTER the action) and without a `verified_at` later than the command's end time. For `released`, require a fresh status query showing the lease gone. Write unknown as `UNVERIFIED`, never as `false`.
*Closes:* "done" without checking state; categorical "absent".

### Rule: absence is not proof of absence · `rule`
> **Rule:** Before claiming "X is missing / not configured / not sent", check ALL sources that can define it (env file, integrations store in the database or admin panel, config, the API response's own state field) and name in the message what was checked. Without a full read, write "not confirmed: only checked Y", never "no".

*Closes:* categorical "absent / not sent / required".

### Rule: cause only after an experiment · `rule`
> **Rule:** Do not call a failure cause established until one of these is done: (a) the code or handler was read, (b) the screenshot or log of the failure was inspected, (c) a control experiment rules out the alternative. Until then write "hypothesis: …, verifying by …". Quote the compiler or test message verbatim; do not paraphrase it into a cause.

*Closes:* hypothesis presented as established.

### Identifiers and paths only by copying from output · `hook`
A pre-write hook for handoffs, receipts, and metadata cross-checks every ID, UUID, path, and type name in the text against an API response, registry, `ls`, or `rg` result from the same session (file exists, ID matches the latest receipt) and blocks the write on an unknown value. An ID the API has not returned yet is never written: query first, hand off second.
*Closes:* wrong name, ID, or path.

### Line numbers and counts from numbered output · `script`
Generate reports with `file:line` references from `rg -n` / `nl` at assembly time and run a check that each `file:line` exists and contains the quoted fragment. Counts in a prompt (35 requirements, 8 files) come from `wc -l` of the list passed alongside.
*Closes:* hand-typed numbers and line numbers; miscounted lists.

### Verify the change is on the production path · `process`
Before writing "deployed / working": `git grep` shows the new module is imported from the entry point at HEAD, and the smoke check of the live site exercises that exact path. For a local environment, pass a readiness checklist (frontend manifest, telemetry read, health endpoint) before announcing "ready".
*Closes:* "done / working" without checking actual state.

### Independent cross-check before handoff · `process`
A report containing claims about someone else's change, a number, or presence/absence is handed over with a source for each item (command or the author's own record). Claims about others' work lacking the author's confirmation are marked `UNCONFIRMED`, which is exactly what coordinators and reviewers were catching after the fact.
*Closes:* hypothesis about cause; unconfirmed claims about others' work.

## Checklist before acting
- [ ] Every number, time, version, and ID in my message was read from a command or record in this session, not recalled.
- [ ] For "done/deployed/released/PASS", I re-read the actual state after the action and have the command plus exit code.
- [ ] For "X is absent", I checked every place X can be defined and named them; otherwise I wrote "not confirmed".
- [ ] Any stated cause is labeled hypothesis unless I read the code, saw the artifact, or ran a control.
- [ ] Claims about another agent's work are marked `UNCONFIRMED` unless the author confirmed.
- [ ] Each `file:line` and path I cite exists and contains what I quote.
