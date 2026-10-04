# 07 · Protocol violations against orchestration tooling

> Agents repeatedly feed the formal contracts of their own orchestration tooling (handoff files, report formats, verification descriptors, immutable registrations, helper CLIs) data in a shape the tool does not accept. Nearly all are rejected by a validator before any damage, but each costs a wasted call, a rebuilt artifact, and occasionally lost or replaced evidence. The same few mistakes recur, so a mechanical template and pre-validation close them better than agent memory. **Share:** 79 of 1,156 recorded incidents (6.8%).

## What goes wrong
- **Checkpoint handoff without the literal status line** (11) — the handoff file lacks `STATUS: CHECKPOINT`, translates the label, uses another status (`NEEDS_CONTEXT`, `READY`), or declares a checkpoint while budget is not exhausted. The registry rejects it; the agent patches one line and retries.
- **Wrong file, directory, ID, or calling context for a checkpoint** (9) — the helper accepts only the canonical handoff in the tickets directory and a registered agent ID. Agents pass a file from a review folder, a segment helper file, a chat ID, an invented hyphenated ID, or call it from a sub-agent context instead of the owning thread.
- **Invalid verification descriptor (inputs and enum fields)** (18) — absolute paths to external tools or packages, recursive folder walks that sweep in old builds and screenshots, incomplete input lists (missing icon asset, debug dylib, UI-test source), stale build-cache paths, a copied previous descriptor, a `kind` outside the allowed set, a list of commands instead of an argument array.
- **Wrong re-admission trigger** (8) — choosing a reason that does not match the real state: a repair trigger with no repair defect of its own, "evidence invalid" instead of "relevant change", "inputs changed" when the fingerprint is identical.
- **Attempts to mutate immutable records** (8) — registering a second time to widen a zone or change cleanup commands, rebinding a reviewer ID, re-creating a finding with an existing ID, overwriting a historical repair receipt or an already-issued report.
- **Report or receipt not matching the parser** (9) — extra paragraphs outside the fixed fields (axis, verdict, checked, findings, blocking), findings without separators, `BLOCKING: no` instead of `none`, field names such as `Credential` rejected as secrets, SHA markers in a disallowed form.
- **Wrong helper-CLI arguments and a lease plan without checkboxes** (16) — missing required fields (agent signature, description, session ID, zone), an object where a path to a JSON file is expected, a message number instead of `file:line`, parallel mutations of a shared journal, and a device/Docker lease plan with no `- [ ]` items or with items already ticked.

## Why it happens
- The agent composes helper input from memory rather than from the helper's schema; the format (literal status line, allowed enum values, `none` vs `no`, checkbox syntax) is known only to the validator and discovered through rejection.
- Copying the previous descriptor or report and editing the prefix carries over stale paths and gaps, and new artifacts (icon, dylib) never reach the input list.
- Input lists are produced by recursive directory walks instead of an explicit version-control file list.
- Paths, IDs, and filenames are guessed instead of read from the registry.
- Immutability of registrations, IDs, and receipts is not known up front: the zone or ID is registered before the full file list is assembled, and the fix is attempted afterward.
- After the first rejection the agent retries without reading usage or the parser; second and third rejections are common.
- Trigger rules lack a single "what changed → which reason" table, so agents pick by similar-sounding names.

## What it costs
- Rejected calls and repeated retries, with rebuilt handoff files, descriptors, and reports.
- Cancelled admissions and new runs (a second descriptor version, several rewritten descriptions) before a build even started.
- Real damage in a few cases: a verification run launched without the icon fingerprint; an overwritten repair receipt leaving the ledger showing an invalid repair with the defect still open; initial evidence temporarily no longer reflecting an issued verdict; two parallel writes to a shared journal that both succeeded but broke the rule.
- Device lease and test run never happened because the plan had no checkboxes.
- Lost state: a malformed checkpoint made resumption ambiguous; a reservation had to be cancelled and changed code re-admitted.

## How to prevent it
### Handoff generator and path-free checkpoint helper · `script`
Provide `handoff-new <agent-id> --status CHECKPOINT|READY|NEEDS_CONTEXT`, which creates the file in the tickets directory with `STATUS: CHECKPOINT` as the first line, in English, never translated. The checkpoint helper takes only the agent ID, locates the canonical file itself, and refuses paths, chat IDs, or files from review folders. On rejection it prints the expected directory and the list of registered IDs.
*Closes:* handoff without status; wrong file/directory/ID.

### Dry-run descriptor validator before admission · `hook`
A pre-tool hook on ledger/admit commands runs `ledger validate <descriptor>` first and blocks on: `kind` outside the registry's allowed set; absolute paths or paths outside the working tree; nonexistent files; paths under build-cache, build-output, or screenshot directories; missing required ID; `args` that is not an array. The message lists the allowed values.
*Closes:* invalid descriptor; wrong helper arguments.

### Explicit input lists from version control · `process`
> **Rule:** Build the `files` list of a verification descriptor only from `git ls-files` of the relevant zones plus explicitly named binary artifacts (icon, dylib, APK) recorded through the internal hash manifest. Recursive folder walks, copying the previous descriptor, and absolute paths are forbidden; describe an external tool through environment parameters.

Verify with `git ls-files <zone> | wc -l` against the descriptor's file count before admission.
*Closes:* invalid descriptor.

### Trigger table driven by a diff · `template/validator`
Add `ledger suggest-trigger`, which compares the fingerprints of the previous and new descriptors and proposes: inputs changed → relevant-change; same inputs but missing coverage → missing-coverage; a repair trigger only if a resolved finding of the agent's own exists. Agents never invent the trigger; they use the command's output.
*Closes:* wrong re-admission trigger.

### Register once, with a preflight plan script · `rule`
> **Rule:** Registration is immutable. Before registering, run `agent-plan` to print the zone, test files, cleanup commands, and session ID, and confirm the list is complete. If you got it wrong, do not register again: register a new agent with a new ID. Never overwrite IDs, repair receipts, or issued reports; a correction is a separate file or record referencing the original.

Make receipts read-only (`chmod 444`) or append-only.
*Closes:* mutating immutable records; wrong helper arguments.

### Review-report template with a linter · `template/validator`
The reviewer fills a template: axis, verdict, checked, findings each with four separator-delimited fields, and `BLOCKING: none` or a list of finding IDs. A `report-lint` script runs before the agent exits and rejects: `BLOCKING: yes/no`, paragraphs outside fields, field names containing credential/secret/token (use neutral names such as `hasAuthField`), SHA markers that are not 64 hex characters. The coordinator pastes the template verbatim into the reviewer's brief.
*Closes:* report/receipt not matching the parser.

### Lease-plan template and checkbox check · `hook`
A hook before the lease command verifies the plan has at least one `- [ ] …` line and no pre-ticked `- [x]`; ticks are added only after a step is done. Generate the plan with the tool's own plan command, not hand-numbered lists.
*Closes:* wrong helper arguments and plan without checkboxes.

### After a rejection, read usage first · `rule`
> **Rule:** After any helper/ledger/lease rejection, run `<helper> --help` or read its parser/schema, fix ALL fields, and only then retry once. Do not guess paths, IDs, or filenames; read the registry. Mutate a shared journal one call at a time.

*Closes:* all subtypes (repeated rejections).

## Checklist before acting
- [ ] I read the helper's `--help` or schema in this session instead of recalling the format.
- [ ] IDs, paths, and filenames come from the registry or `ls`, not from memory.
- [ ] The descriptor's file list comes from `git ls-files` plus named artifacts, with no absolute paths and no folder walk.
- [ ] I ran the dry-run validator or linter and it passed before the real call.
- [ ] The action is not a re-registration or an overwrite of a receipt, ID, or issued report.
- [ ] The lease plan has `- [ ]` items, none pre-ticked.
