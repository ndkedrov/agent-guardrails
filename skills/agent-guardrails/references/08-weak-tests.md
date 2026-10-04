# 08 · Weak and wrong tests and evidence

> Agents write tests, verification scripts, and evidence that either pass on broken code or fail on correct code: wrong oracle, wrong precondition, no wait for readiness. Many of these gaps were caught only by independent review, and a number of records state that the test had not even been run yet or failed before reaching the feature. **Share:** 57 of 1,156 recorded incidents (4.9%).

## What goes wrong
- **Test could pass on broken code** (12) — assertions too weak: a `zip` comparison without checking length, a total count instead of "one per height", an `assert` that disappears under `NDEBUG`, 20 × `Task.yield` instead of awaiting completion, a fixture where the error never reaches the handler under test.
- **Oracle too strict or wrong, giving false failures** (15) — expectation tighter than or different from the contract: JSON key and array order, `"5.00"` vs `"5"`, "no data" vs "unknown", strictly positive normal where zero is allowed, SHA-256 of bytes when a proxy obfuscates emails, a `Token=` substring inside a `HasToken == true` check, a closing parenthesis assumed after the first argument, identical parameter sets after a remux.
- **Wrong precondition or fixture before the feature is exercised** (12) — the test dies before reaching the behavior: `chmod 0400` while running as root, a schema file missing from an isolated copy, a test client without a local address (all seven tests), a "paused" precondition when ready/offline is legal, a bootstrap path without `realpath`, stub players missing a new method, `update` instead of `forceFill`, a stub that wipes data, a non-default simulator port.
- **No readiness wait or async race** (8) — UI test or script outruns state: UI dump right after launch (null root), reading a draft before a deferred write, tapping a button before permissions load, stale accessibility cache, continuing after `ok=false`, a shared link cleared before expansion, diagnostics written after the check that already failed.
- **Evidence screenshots do not show what must be proven** (5) — numbers match but the frames lack the receipt: keyboard covers the lower part, extra swipes, a partially visible header accepted as enough, a prefix glob that picked up old files, an English screenshot that stayed in the source language because of a stale container.
- **Evidence and hashes do not match what was actually used** (5) — hash evidence omits input files the test really read (feature catalog, icon), a compiler version recorded while `CXX` is overridden, a copied scenario pointing to an old receipt, a method boundary hashed with a blank line or without the added comment.

## Why it happens
- The test is written to match the agent's expected result rather than the public contract, even when the contract was already in code or a catalog.
- Nothing proves the test can fail on broken code; weak assertions (count instead of set, one vector component instead of the vector) surfaced only in independent review.
- Environment preconditions (root, schema, local address, server state, UID, port) are not checked inside the test, so it fails before testing anything.
- Readiness is guessed (yield × 20, instant dump, fixed swipe count) instead of waiting on a named signal.
- Evidence (hashes, receipts, screenshot selection) is assembled by separate manual code and never reconciled with what the test read or showed.
- A numeric or logical check is treated as sufficient for a visual requirement; the frame is never checked for the required element.

## What it costs
- Whole suites ended before the feature was exercised (all new tests of a feature, the first UI dump with no root, a login/scan check on a device).
- Product behavior stayed unconfirmed while the test was still unrun.
- Real defects could slip through: a lost edge vertex, duplicate faces, repeated video rotation, an unsafe response in a late request, a Release build that never calls the library.
- Correct artifacts were rejected: HTTP 200 with the right hash, an export with unchanged video data, a good run with a valid permutation.
- Visual verification of financial receipts failed several times and scenarios had to be redone.
- Wasted runs and build-queue time; a rejected run; a test app's automatic settings restore did not execute.

## How to prevent it
### Mandatory negative control for every new test · `rule`
> **Rule:** A new or changed test is done only after you prove it goes red: introduce a minimal break in the code under test (remove a line, flip a sign, drop a vertex, duplicate an element), run the test, record in the report what you broke and that the test failed, then revert. A test without this record counts as unverified. For every collection comparison check count, uniqueness, and completeness separately, not just values via `zip`.

*Closes:* test could pass on broken code.

### Banned-pattern test linter · `script`
A pre-commit/CI script that fails on: calls with side effects inside `assert` (C/C++ without an `NDEBUG` guard), N × `Task.yield` or bare `sleep` instead of a wait, `XCTAssertEqual`/`assertSame` on arrays and JSON objects without order normalization, `zip` without a prior length check, comparing a single vector component. Keep the pattern list narrow (`rg -n 'Task.yield|sleep\(' tests/`).
*Closes:* could pass on broken code; too-strict oracle.

### Cite the contract before the expected value · `rule`
> **Rule:** Before writing an expected value into a test, cite its contract source (public API, localization catalog, schema, spec) as file and line in a comment or the report. Compare only what the contract guarantees: key and array order, number format, zero components, the "unknown" text. For hash comparisons state what is hashed (bytes or decoded text) and which normalization (email obfuscation, parameter sets after remux) is permitted.

*Closes:* too-strict or wrong oracle.

### Preconditions inside the test · `template/validator`
A test template with a preconditions block that fails with an explicit `PRECONDITION` message, never as a feature failure: UID != 0 for permission tests, schema and files present in the isolated copy, test client with a local address, initial server state (paused/ready/offline allowed for a cold start), `realpath` for bootstrap, stubs implementing every protocol method. A failed precondition is not counted as a failed feature.
*Closes:* wrong precondition or fixture.

### Readiness-wait helper instead of guessing · `script`
One utility set for UI and async tests: `waitFor(condition, timeout)` with a named signal (element exists and is hittable, root not null, draft written, permissions loaded), accessibility-cache invalidation before lookup, `scrollTo(element)` instead of fixed swipes, and a helper that stops the scenario on `ok=false`.

> **Rule:** `Task.yield` × N, unconditioned sleep, and fixed swipe counts are forbidden; every wait names its signal.

*Closes:* missing readiness wait or async race.

### Automated check of the evidence frame · `template/validator`
For each screenshot step declare what must be in frame (receipt title, validity period, card top) and check its `isHittable`/visibility within screen bounds before the capture; dismiss the keyboard explicitly; select files by the exact names of the current scenario, never by prefix. A frame without this check is not accepted as visual evidence.
*Closes:* screenshots do not show the proof.

### Derive evidence dependencies mechanically · `script`
The evidence script collects hashes from a trace of files the test actually opened (`strace`, `fs_usage`, or an `open` wrapper) or from a dependency manifest the test itself declares; the compiler and version come from the effective `CXX`. A separate test confirms that changing each dependency invalidates the evidence. Hash methods by AST or line range, not by a hand-cut slice.
*Closes:* evidence and hashes mismatch what was used.

### Test review before the first run · `process`
For oracle tests (geometry, finance, contracts) add a gate: an independent reviewer reads only the test and the public contract and hunts for false accepts and false rejects, before any build. In the records this step caught nine gaps; make it a formal gate, not luck.
*Closes:* could pass on broken code; too-strict oracle.

## Checklist before acting
- [ ] I broke the code under test on purpose and watched this test fail, then reverted.
- [ ] Each expected value cites a contract source (file:line), not my expectation of the output.
- [ ] Collection assertions check count, uniqueness, and completeness, not just paired values.
- [ ] Preconditions (user, files, address, server state) are asserted with a distinct message before the action.
- [ ] Every wait names its signal; no sleep, yield-count, or fixed-swipe waits.
- [ ] Evidence hashes cover every file the test read, and each screenshot is checked for the required element.
