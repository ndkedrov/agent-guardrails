# 10 · UI defects and broken UI tests

> Roughly a quarter of these incidents are real layout or rendering defects in the product (clipping, overlap, collateral CSS edits, raw identifiers, a zero timer). The rest, about three quarters, are defects in the UI tests and screenshots themselves: wrong selectors, no waiting, clicks on stale coordinates, a frame of the wrong route or viewport. Most were caught before commit, but runs failed and had to be repeated, and several mobile scenarios stopped before the feature under test was ever exercised. **Share:** 34 of 1,156 recorded incidents (2.9%).

## What goes wrong
- **Wrong or ambiguous selector / element type in a UI test** (13) — the test looks for an element by a label that also matches another control, by global text not scoped to a dialog, by an assumed element type (a generic container instead of a collection), by stepper index, by a merged semantics node that does not exist, or inside a container that is absent. The test fails before the feature is exercised.
- **Test does not wait for UI state** (6) — the action or assertion runs right after navigation: the window is not yet present, a system confirmation dialog is unaccounted for, the IME keyboard is still open, the Compose hierarchy is momentarily empty, the app is still loading.
- **Navigation by stale coordinates or geometry** (3) — the agent taps coordinates from a previous screen state, or "the nearest clickable element below the title", and lands on a different screen or opens the wrong settings.
- **Screenshot of the wrong screen or viewport** (2) — a frame is saved under another screen's name, or at the wrong width (desktop instead of phone), because route and viewport were not verified. A diagnostic shot taken after the app exited showed the home screen.
- **Layout: clipping, overlap, stretching, collateral styles** (6) — columns with content-based min-width break a 1280 px layout, date fields do not fit a phone, a video surface covers the status row, a weight in a nested block hides a name, cards in a pair differ in height, an extra CSS edit changes unrelated buttons.
- **Functional display error** (3) — an element never appears because it hangs off an empty loop container, a timer shows zero for a fresh QR code, raw enum values (`classic`, `silver`) show instead of localized names.
- **Other** (1) — data-entry mistake in a web editor (an interval start set before the previous end was extended).

## Why it happens
- The test is written from assumptions about the accessibility tree (element type, merged vs. unmerged semantics, presence of a system title, stepper button order) instead of from an actual dump.
- Selectors rely on visible text, role, or index without container scoping, and the page has several matches.
- There is no explicit wait-for-state (idle/waitFor) between action and assertion; it is added only after the first failure.
- Clicks are computed from coordinates or geometry, and the current screen is not confirmed before each step.
- Screenshots are taken without checking URL/route and viewport; browser state is left over from the previous step.
- Layout is checked at one width or one device only, and CSS edits are not reviewed by diff for side effects.
- Conditional rendering is attached to a temporary container (empty loop, nested weighted block) and never verified against a real state.

## What it costs
- UI test runs failed before reaching the feature under test and had to be repeated.
- Several runs stopped before the import/confirm step, so the feature could not be counted as verified until the test was fixed.
- A diagnostic frame that shows the wrong screen is not evidence; a functional check was not credited because the test itself was wrong.
- Wrong frames and a stray CSS edit nearly reached a commit or publication, caught only by manual review.
- A user had to point out defects from screenshots that the agent's own check had missed.
- Risky taps landed in unrelated settings screens, and one wrong interval was added in an editor (no data was exported or changed permanently).

## How to prevent it
### Dump the UI tree before writing a selector · `rule`
Take a dump of the element tree for the screen under test and use the type, tag, or accessibility id that is actually in the dump. Save the dump with the run artifacts.
> **Rule:** Before writing or changing a UI-test selector, dump the element tree for that screen (XCUITest `debugDescription`, `adb shell uiautomator dump`, Compose `printToLog`, Playwright aria snapshot) and use the type, tag, or accessibility id that is actually present. Do not rely on an expected type, text, index, or merged node.

*Closes:* wrong or ambiguous selector.

### Stable identifiers and scoped lookup only · `rule`
Add the identifiers to product code in the same change as the feature.
> **Rule:** In UI tests, find every interactive element by `testTag` / `accessibilityIdentifier` / `data-testid` defined in product code, never by text, role, index, or coordinates. For lists and dialogs, scope the query to the container. A selector that matches more than one node is a test bug.

*Closes:* wrong selector; navigation by coordinates.

### Shared helpers with mandatory waiting · `script`
Keep one helper module per test project (`waitForTag`, `waitForElement`, `tapWhenReady`) whose timeout survives a temporarily missing window, an empty Compose hierarchy, and a system dialog, and which saves a screenshot and the tree on failure. Add a CI lint: `rg -n '\.(click|tap)\(' tests/ | rg -v helpers` must be empty. Close the keyboard only through a helper that checks window insets / IME state.
*Closes:* test does not wait for UI state.

### Confirm the screen before each navigation step · `rule`
> **Rule:** Before every click in a UI verification sequence, confirm the current screen (activity, title, or URL from the dump). Never reuse coordinates or order from an earlier pass. If there is no tag, add one to the product code first.

*Closes:* navigation by stale coordinates.

### Screenshot wrapper with self-labelling · `script`
`shot <name> --expect-url <route> --viewport <W>x<H>`: opens or checks the URL, sets the viewport, refuses to save when URL or size differ, and writes URL and size into the file name and metadata. Require a separate pass at 390 px for mobile layout.
*Closes:* wrong screen or viewport.

### Layout matrix and a diff review for collateral styles · `process`
For CSS/layout changes capture frames at 390, 768, and 1280 px (web) and on a small and a large phone (iOS/Android). Before commit, `git diff -- '*.css'` must contain only selectors named in the task; unrelated hunks are reverted. For paired cards (iOS/Android) add a test for equal row height and grouping by bundle id.
*Closes:* layout defects, collateral styles.

### One UI test per conditional element, in a real state · `template/validator`
In the ticket template, list every display condition ("shortcut visible to the cashier", "timer not zero for a fresh QR", "level shown as localized name, not raw enum") and require one UI test per condition with data that reproduces it. Do not hang conditional rendering off an empty loop or a nested weighted block; use a permanent container.
*Closes:* functional display error, layout.

### A failed test never counts as verified · `rule`
> **Rule:** If a UI test fails before confirming the action under test, report "not verified", not "verified". Re-run only after fixing the test, and name the cause (test or product) with a link to the screenshot or dump.

*Closes:* all test-error subtypes.

## Checklist before acting
- [ ] I dumped the element tree for this screen and my selector matches the dump.
- [ ] Every selector uses a product-defined id and is scoped to its container; it matches exactly one node.
- [ ] Each action goes through a wait helper; no bare tap/find.
- [ ] I confirmed the current screen/URL and viewport before each step and before each screenshot.
- [ ] For layout changes I have frames at all required sizes and a CSS diff with no unrelated hunks.
- [ ] I looked at every screenshot for clipping, overlap, raw identifiers, and zero or placeholder values before calling it done.
