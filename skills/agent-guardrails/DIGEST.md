AGENT GUARDRAILS (from 1,156 real agent incidents). Apply all session; full rules: skill "agent-guardrails".
1 Paths: only from this session's listings (rg --files, ls, git ls-files) or the task text. Not found once -> list, never guess twice. Absolute paths for edits/builds; never chain edit;build with ';'.
2 Reads: wc -c first; one file per call, by range. JSON/logs: named fields only (jq). Truncated = unread; re-read the gap. Scoped searches, never ~ / build dirs.
3 Code: read result = loaded|empty|FAILED; failed never means empty and blocks writes. Async results carry request/session ids; drop stale ones. Compare real types. Build after the last edit.
4 Tools: read --help before unfamiliar CLI flags. Quote globs. No non-ASCII source via python3 - or -c; write a file. One patch op per file. Fresh UI snapshot after every screen change.
5 Shapes: print type/keys before parsing JSON; print schema before SQL; rg a symbol's definition before using it.
6 Order/scope: start dependent steps only on a confirmed ready signal. Don't touch frozen verification inputs. Stay in scope (git diff --name-only). On servers/shared trees: read state and owners first; never restart/push/deploy over others.
7 Protocols: fill handoffs/reports/descriptors from templates; exact keywords/enums. IDs and registrations are immutable. After a rejection read the usage, fix all fields, retry once.
8 Tests: prove each new test fails on broken code. Assert only contract guarantees (cite file:line). Explicit PRECONDITION checks. waitFor(state), never sleep.
9 Claims: "done/works/released" only with this session's evidence. Absence of evidence != absence. Causes are hypotheses until verified. Copy IDs/numbers/file:line from output.
10 UI: selectors from a UI tree dump (test ids, scoped); confirm the screen before each step; verify viewport/URL before screenshots.
11 Delegation: briefs self-contained; mandatory blocks pasted verbatim; verify every path in the brief; release shared resources by exact id.
12 Requirements: before "done", map every task and standing-rule requirement to evidence; check the result as the user sees it.
13 Secrets: never print .env*, signing/credential files, docker compose config, docker inspect, process args. Filter before output. If leaked: say so, recommend rotation.
Before "done": evidence per requirement; built+tested after last edit; diff in scope; no git add -A; unverified items labeled.
