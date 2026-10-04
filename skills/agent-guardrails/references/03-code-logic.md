# 03 · Logic Errors in Product Code

> The agent writes code whose logic does not cover failure, stale state, data boundaries or platform behavior. The usual areas are desktop and mobile clients (saving, sessions, response races), geometric algorithms in a 3D scanner, and server-side analytics. The author rarely catches it: independent review, a local UI run/test or the compiler does, and in about a third of the cases the code had not even been run when the defect was found. Only a handful of defects reached production; the rest were stopped before deploy. **Share:** 142 of 1,156 recorded incidents (12.3%).

## What goes wrong
- **Data loss, overwrite or stale state after a read/write failure or a race** (47) — after a failed read or save the code leaves an empty state and allows writing over unknown data; a late async response, a parallel save or an old state (draft, error, lease, cache) overwrites the current one. The critical part was found only by static review.
- **Algorithm and numeric errors in geometry/3D export** (24) — wrong conditions: zero confidence treated as an error, missing data treated as zeros, local indices used instead of global, forced volume sign, quadratic complexity, overflow on multiplication, wrong units or color channels, a non-closed export mesh.
- **Compile errors before the first build** (12) — complex expressions without explicit types, name shadowing, a missing bracket, argument order, `try` in a shorthand expression, an unqualified `max`, a renamed modifier. All stopped by the compiler or a self-check before release.
- **Comparing or parsing data of the wrong type or shape** (15) — a string compared with a date, a hash with an array, an interpreter path with a launcher path, nullable with nullable, UTC used without conversion to local time, missing case/whitespace normalization, a parser that takes a template instead of values, exception handler order (a timeout caught as a generic OS error).
- **Server defects in Laravel/Livewire/SQL: memory, variables, middleware groups** (14) — undefined variable/key in templates and closures, loading raw rows past a 128 MB limit, sorting large JSON, a throttle in the `web` group instead of the admin-panel group, mass-assignment in `firstOrNew`, an index name over 64 characters, a reactive proxy passed to `structuredClone`.
- **Wrong domain business logic** (16) — unaccounted invariants: expired bonuses restored, status kept after a visit is cancelled, a financial block hidden on suspension, quiet hours bypassed, sales zeros without currency, wrong classification of a device source, a stale target duration.
- **Unverified assumption about a platform, tool or format** (14) — actual behavior was not checked: an HLS player without `seekable`, `ffprobe` without `duration_time`, padded AAC samples, an unescaped `%` in a format string, an implicit Android intent, `KeepAlive` with a slot, bracketed paste in a terminal, a 45 s readiness check for a 103 GB operation.

## Why it happens
- After an error (read, write, cancel, network failure) the agent did not walk the failure branch: an empty state was taken as "no data" rather than "could not read".
- An async response, lease or draft is not tied to a request/version/session id, so a late result overwrites the current one.
- The author's tests repeat the author's assumption: a test covered only the cloud source while the fixture used a non-canonical local one; unit tests for HLS passed while a real browser failed.
- Actual platform/tool behavior was not checked before writing code (ffprobe, HLS seekable, Android intents, format strings).
- For Windows/macOS/iOS clients the runtime is missing or execution is deferred, so only static review finds defects, not a run.
- Complex expressions without explicit types and mechanical regex-based replacements.
- No shared tooling for known traps (128 MB memory limit, admin-panel middleware groups, the 64-character MySQL identifier limit, JSON sort limits); each was found only on the server or in a local test.

## What it costs
- Three production symptoms: an ERROR in the log from sorting large JSON, a 128 MB limit breach with a user-visible notification, an "Undefined array key" on an analytics tab.
- HTTP 500 on an analytics page and in loyalty-app tests.
- Risk of losing or overwriting user data (local systems, guest pairing, 3D scans, drafts) identified in code, with no confirmed loss.
- Wrong data for the user: zero metrics instead of unknown, extra frames in video, lighter colors in a 3MF export, expired bonuses in a balance, `5.00` shown instead of `5.00%`.
- Wrong first attempts by the user: a key rejected as "does not look valid", choppy video playback, a card not rendered because of a `%` format on Android.
- Extra edit/rebuild/test cycles and acceptance blocked until a fix.
- An unfinished timeout in a server-update helper after the process had already started.

## How to prevent it
### Three read states: "failed" is not "empty" · `rule`
**Rule:**
> Any read of a file/session/cache returns a Result with three states: Loaded, Empty, Failed. Failed blocks save, delete and overwrite until a retry succeeds. An empty list after a read error is forbidden: return the error, not `[]` or `nil`. For every new store add a test: the read throws, then save/delete are rejected.

*Closes:* data loss / overwrite / stale state.

### Request/version token on every async result · `rule`
**Rule:**
> Every async request that writes state carries a monotonic request id plus the session/account/source-version id. Compare all of them before writing a result and drop a stale one. On account, session or source change, clear drafts, errors and models in one place. A test with controlled response order (slow first, fast second) is mandatory.

*Closes:* data loss / stale state; races.

### Failure checklist before handing over for review · `template/validator`
Require a section in every task description: "For each change that writes data list: (1) what happens if read/write fails; (2) what happens if the response arrives late or twice; (3) what happens with empty/nil/zero input; (4) range boundaries (0, NaN, Inf, duplicate indices)". A completion hook rejects a report that lacks the section or lacks a regression test for each item.
*Closes:* data loss/state; algorithms and numbers; data comparison.

### Blocking compile gate before saying "done" · `hook`
A Stop hook for Swift/Kotlin/C#: if the diff touches `*.swift`/`*.kt`/`*.cs` and no successful build of that target ran after the last edit, forbid finishing with "build before finishing". **Rule:**
> Write complex expressions (map with SIMD, SwiftUI text concatenation, three Floats into a Double) with explicit intermediate types; check for name shadowing, an unqualified `max`, and initializer argument order. Use a static linter (for example SwiftLint) with a rule against long expressions.

*Closes:* compile errors.

### Typed comparison of dates, time and sources · `rule`
**Rule:**
> Compare dates only via `whereDate` / `Carbon::toDateString()` and timezone conversion; never compare a string with a datetime. Convert API times from UTC to the user's local time zone before formatting. Classify a source (board/local/cloud) in one shared function with trim + lowercase and a test for whitespace, case and unknown values. Check nullable == nullable together with has-value.

Add shared fixtures with non-canonical values beside canonical ones.
*Closes:* comparing data of the wrong type.

### Guard tests for known Laravel/Filament/MySQL traps · `script`
Add to CI (run LOCALLY, never against production): (a) a render test of every analytics tab with empty data and with `memory_limit=128M`; (b) a check that every created index name is at most 64 characters (iterate migrations); (c) a feature test that the throttle applies to the real admin-panel route, not just the `web` group; (d) a lint that forbids `select *` / `orderBy` on models with JSON columns in analytics.
**Rule:**
> Run tests with an explicit `APP_ENV=testing`; a wrapper such as `./t` sets it automatically.

*Closes:* Laravel/SQL server defects.

### Experiment on the real platform before coding · `process`
**Rule:**
> For HLS, `ffprobe`, Android intents, format strings and terminal input, first run a minimal experiment on the real platform (Docker `ffprobe`, an emulator, a real browser) and record the result in one line before editing. A unit test without the real platform does not prove behavior.

For percent format strings add a test that runs every locale through the real `String.format` / `String(format:)`.
*Closes:* unverified platform assumptions.

### Early independent review for clients that cannot be run · `process`
For Windows/macOS clients where C# or Swift cannot be executed, plan first a skeleton with public scenario tests for every failure branch, then review contracts against the mobile reference (field list, normalization, canonical values) BEFORE writing UI. Add a static checklist per task: what changes the session, what clears it, what blocks it.
*Closes:* data loss/state; wrong business logic.

## Checklist before acting
- [ ] I traced the failure path: what the code does when a read, write or request fails.
- [ ] A late or duplicate response cannot overwrite newer state (request id + session/version compared).
- [ ] Empty, nil, zero, NaN and duplicate-index inputs were considered and tested.
- [ ] Domain invariants (expiry, cancellation, suspension, quiet hours, currency) are listed and each has a test.
- [ ] Platform/tool behavior I rely on was checked by a real minimal experiment, not assumed.
- [ ] The changed target compiled after my last edit, and tests ran locally, not against production.
