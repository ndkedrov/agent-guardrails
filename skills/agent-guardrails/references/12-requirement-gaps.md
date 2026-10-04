# 12 · Unmet or incomplete requirements

> Agents reported work as complete while part of an explicit requirement was still unmet: a limit missing from an overview, incomplete export metadata, a framework linked but never called, a build number not raised, the wrong directory or language. Most were found not by the agent but by the user, an independent review, or a store rejection. What they share: the definition of done in the request was never compared with what was built before saying "done". **Share:** 22 of 1,156 recorded incidents (1.9%).

## What goes wrong
- **Partly implemented requirement reported as complete** (6) — one part of the requirement was built and the rest skipped: a cap on the number of items in an overview, per-material metadata not written to an export, a patch-level quality score instead of an overall one, a camera without a position, a required framework present only as a dependency, a session closed with the web version unfinished.
- **Wrong object or wrong client verified** (2) — the agent checked a cheap proxy (a document, a freshly started client) instead of what was required: the lifecycle of a map, an already-open old web panel.
- **Explicit process rule or mandatory registry skipped** (7) — the build number was not raised, the marketing version was not checked before an upload, a new screen was not added to the screen registry, test files went to the wrong directory, an internal handoff was written in the wrong language, unescaped angle brackets broke a Markdown report, or two 45-second waits went by without a progress message although updates were required every 60 seconds.
- **Technically done, but not convenient or not what the user meant** (5) — an interface that lists raw API metrics with duplicates and UTC times, a studio address with no one-time connection step, one address given for two requested pages, internal captions and five descriptions on a site, a video prompt that never says who is speaking.
- **Incomplete public contract for independent tests** (2) — the API or cleanup description left out the exact thresholds and conditions in force (minimum index count, an RMS bound relative to the limit, criteria for small and floating components), so the test author could not choose fixtures.

## Why it happens
- Nothing maps what was built onto the list of requirements before "done": the agent checks that the added thing works, not that the whole requirement is covered.
- A convenient substitute is verified: a document instead of the map lifecycle, a fresh client instead of the stale open panel.
- Mandatory actions that live in global rules or registries outside the current task (build bump, screen registry, report language, update cadence) are not in the task checklist and depend on memory.
- External state (the marketing version in the store backend) is not checked before the action that depends on it.
- User requirements are read literally and technically (an address, a limit, "30 days") without asking whether the result is convenient and unambiguous for a person.
- A contract is described from memory of the intent, not read back from the current implementation with all its conditions and thresholds.

## What it costs
- The user repeated the same complaint (a map that reloaded; the same address for two pages).
- A store upload was rejected because the marketing version was already published, forcing a new archive.
- The app stopped on a clean launch because a screen was missing from the registry.
- A slicer showed every logo colour under one material, so the output was unusable for multi-colour printing.
- An iOS build had to be prepared again as a separate release artifact because of a stale build number.
- An independent test author could not derive correct fixtures from the published contract.
- The user got no updates for over 60 seconds while workers ran; interface, site copy, and a prompt were redone.

## How to prevent it
### Requirement checklist in every task and a "requirement → evidence" report · `template/validator`
Before replying "done", list every explicit requirement from the task and from the global rules (number, limit, format, language, mandatory frameworks, every "all/each") and attach evidence to each: `file:line`, a command with its output, or a screenshot.
> **Rule:** Do not write "done" until every requirement has a "requirement → evidence" line. A requirement without evidence is reported as unmet, not dropped. Words like "all", "each", "mandatory" are verified by an exhaustive list, not a sample.

*Closes:* partly implemented requirement; incomplete public contract.

### Hook on iOS build and upload: build number and marketing version · `hook`
PreToolUse on `xcodebuild archive`, fastlane, and store upload: compare the current build number in `project.pbxproj` with the one at the last commit that touched Swift code, and block if it was not increased. Before uploading, query the store backend for the marketing version's state and block if it is already published.
*Closes:* skipped process rule (build number, marketing version).

### Registry guard test for screens and routes · `script`
A unit test enumerates every screen registered by the modules and fails when any is missing from the screen registry (and vice versa). Run it in the default suite and before each commit.
> **Rule:** A new screen means a registry entry in the same commit; the registry test must pass.

*Closes:* skipped process rule (registry).

### Verify the real framework, not the link · `script`
For each library the spec requires (for example a vector-math framework), a script greps the sources for calls to its symbols (`rg -n 'vDSP_|cblas_' Sources/`) and fails when only an import or dependency entry exists.
> **Rule:** A requirement to use a framework is met only when its API is called in the computation path; linking it in the project does not count.

*Closes:* partly implemented requirement.

### Verify the claimed property on the artifact and on an old client · `rule`
> **Rule:** Check what was claimed on the result itself: for an export, the file content (slicer metadata, not just geometry); for a UI state, behaviour (is the map recreated, does the page reload); for a protocol change, also an already-open client of the previous version. Checking a document, a fresh client, or only geometry does not confirm completion.

*Closes:* wrong object verified; partly implemented requirement.

### Mandatory-actions checklist in the completion template · `template/validator`
A final-report template with boxes: report language is the one requested; test files only under the designated directory; Markdown free of unescaped `<...>` (run a Markdown linter with a no-inline-html rule on the report); progress message at least every 60 seconds, so any single wait is at most 45 seconds.
> **Rule:** A single wait is at most 45 seconds; between two waits there is always a progress message.

*Closes:* skipped process rule (directory, language, escaping, cadence).

### Derive the contract from code and have the test author check it · `process`
> **Rule:** A public contract lists every current numeric threshold, entry condition, renumbering/attribute-preservation rule, and known limitation, quoting the constants from the code. After writing it, list the input classes (valid / invalid) for which a test author can unambiguously choose a fixture.

*Closes:* incomplete public contract.

### Review usability before handing over · `rule`
> **Rule:** Before handing over an interface, link, or text, view it as the user would: no API metric names, no duplicates, dates and times with the user's local time zone stated, periods whose calendar-day count matches the label, access including every step (a fresh connection code), and a separate answer for each separate question (two pages = two different addresses, or an explicit "not found"). If it changes the result, ask who the audience of a text is (for example, who is speaking in a video).

*Closes:* technically done but not convenient.

## Checklist before acting
- [ ] I extracted every explicit requirement, including "all/each/mandatory" words, from the task and the global rules.
- [ ] Each requirement has evidence (file:line, command output, or screenshot); unmet ones are listed as unmet.
- [ ] I verified the real object (artifact content, lifecycle, old client), not a proxy.
- [ ] Build number, marketing version, and screen/route registries are checked before any release step.
- [ ] Report language, file location, and update cadence match the rules.
- [ ] I read the result as the user would and answered each question separately.
