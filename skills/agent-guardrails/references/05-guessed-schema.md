# 05 · Guessed data structures and APIs

> Agents write one-off scripts, SQL queries, DTOs and API calls against an assumed data shape without checking the real file, schema, contract or documentation. Almost half of the cases are three identical mechanical slips in the agents' own helper scripts. Damage is mostly small (the script fails before changing anything), but some cases ran tests against the wrong database, left a batch edit half-applied, or pushed without the new files. **Share:** 113 of 1,156 recorded incidents (9.8%).

## What goes wrong
- **Rules index read as a dict** (25) — a script reading a local rules/memory index calls `projects.items()`/`.get()` although `projects` is a list; `AttributeError` at the start of many independent sessions, each rediscovering it.
- **Own JSON logs, receipts and `xctestrun` misread** (21) — list read as dict and vice versa, a count treated as a collection (`len()` of a number), a key at the wrong level (`runs` not at root, no `TestConfigurations`, `result` instead of `receipt`), a hash compared to an argument array.
- **Docker `IPAM.Config` is `null`** (6) — a free-subnet check assumes `IPAM.Config` is always a list; for a system network it is `null`, so `TypeError` before any resource is created. The same script was rewritten many times.
- **Guessed SQL tables and columns** (10) — read-only queries against local SQLite/MySQL with invented names (`commit_hash` for `commit_sha`, non-existent activity or finance tables, `history` for `period_history`, an API field used as a column), or one tenant filter applied to every table even after the schema had been read.
- **Invented server/API contract fields and enums** (18) — DTOs, decoders, request bodies and external-API calls written from memory: wrong JSON keys (`alarms`/`items` instead of `events`), wrong enum values, string instead of int, wrong limits (6-64 A instead of 7-48 A), extra or missing required fields, metric dimensions, a `locale` in a PATCH.
- **Non-existent method, property, import or argument** (24) — calls to a library/SDK/own function that does not exist or has another shape: a class from the wrong package, a test helper without its dependency, SIMD functions without import, a property absent on a UI container, `is_valid` called as a method, an unsupported keyword argument, a state call missing on a browser driver.
- **Wrong assumption about environment, fixture or format** (9) — trusting expected behavior: `phpunit.xml` assumed to override a container's `DB_DATABASE`, an image assumed to include `pytest`, a fixture assumed to persist a value, an API assumed to return 200 (it returns 201), a "valid" profile that is below the allowed minimum, XPath indexes applied to an object instead of its parts.

## Why it happens
- The script or query is written "from the head" with no reconnaissance step: no `type()`/`keys()` print, no migration, DTO or doc read.
- Routine operations (read the rules index, check a Docker subnet, read a verification log) are improvised anew by each session, so the same bug recurs even though the correct form is known.
- There is no single source of structure: the canonical server contract (DTOs, enums, bounds) lives in another repository, so native-client agents write from memory first and verify later.
- The error is caught by an expensive late stage (compilation, a 13-test run, a 400 from a store API, manual QA) rather than a cheap check before writing.
- Protective settings are trusted instead of asking the system: `phpunit.xml`/`force` instead of the live `DB_DATABASE`, a JSON "list" instead of a type check, a list instead of `null`.
- Even a schema that was already read is not used when writing the next query.
- Large combined reads without a limit get truncated and force re-reading files that were already known.

## What it costs
- Scripts crash before making changes (`AttributeError`, `TypeError`, `KeyError`); the read is repeated, and in many sessions the first step is spent on the rules index.
- A batch edit stopped halfway, leaving some platform markers and one page partly updated.
- Tests run against the wrong database; a parallel run produced `database is locked` and the full run had to be stopped.
- A WebSocket suite closed at `hello` because of an invalid profile; the failed run had to be recorded and the fix handed to another worker.
- A push without the new files, so metadata never reached the repo; store APIs rejected requests (HTTP 400) for a wrong locale or fields; a temporary store "edit" draft had to be deleted.
- A verification step that did not run or did not pass risked a false "passed"; a dependent command ran after its predecessor failed.
- Code that would not compile or deserialize was saved only by a pre-run self-check; without it the damage would have reached users.

## How to prevent it
### One script for the rules index · `script`
Provide a `rules-lookup <project>` tool (Python) that knows `projects` is a list, matches by name/path, and prints the entry with bounded output. Add a test against the real index file.
**Rule:**
> Read the local rules index only with `rules-lookup <project>`; do not write your own `json.load` scripts for it.

*Closes:* rules index as dict.

### One script for a free Docker subnet · `script`
Move the logic into a `docker-free-subnet` script using `(net["IPAM"]["Config"] or [])`, and have the lease manager's Docker claim call it.
**Rule:**
> Check Docker subnets only with `docker-free-subnet`; `IPAM.Config` can be `null`.

*Closes:* Docker `IPAM.Config = null`.

### "Shape first, then code" for JSON and SQL · `rule`
**Rule:**
> Before any script that reads JSON, print the structure first: `python3 -c "import json;d=json.load(open(F));print(type(d).__name__, list(d)[:20] if isinstance(d,dict) else type(d[0]).__name__)"`. Before SQL run `.schema <table>` / `PRAGMA table_info(<table>)` / `SHOW COLUMNS FROM <table>` and use only the printed names. Every value used with `len()`, `.items()` or `.get()` must have its type confirmed.

*Closes:* own JSON logs; guessed SQL columns.

### Shared loader for logs, receipts and `xctestrun` · `script`
One `load_runs()`/`load_receipt()`/`load_xctestrun()` in a shared module validates the shape (JSON Schema or dataclass) and fails with "expected X, got Y". It never substitutes `0` for a missing field.
**Rule:**
> Read logs and receipts only through this library.

*Closes:* own JSON logs, receipts, `xctestrun`.

### Machine-readable API contract plus a parity test · `template/validator`
Export from the server an OpenAPI/JSON Schema (or a list of DTOs, enums and bounds) into one file in a shared folder. Task briefs for client agents must say: "read `contract.json` before writing the model; do not add fields it does not list." Add a test that compares each client's `CodingKeys`/enums with the file and fails on any divergence.
*Closes:* invented contract fields and enums.

### Hook: no SQL before the schema · `hook`
PreToolUse on Bash: if the command contains `sqlite3`, `mysql`, `psql` or `php artisan tinker` with SELECT/UPDATE and none of `.schema`, `PRAGMA`, `SHOW COLUMNS` or a read of that table's migration appears in the last N calls, reject with "print the table schema first". Apply the same to production read-only queries.
*Closes:* guessed SQL tables and columns.

### Verify a symbol before using it · `rule`
**Rule:**
> Before using a method, property or import you have not seen in this repository, find its definition: `rg "<symbol>"` in the code or in a local dependency (jar, xcframework, docs); for an external SDK open the docs. Add an import only from the package where the symbol was found. Do not write a call you cannot confirm from a source.

Run a fast single-file compile after every new edit instead of at the end (`swiftc -typecheck`, `kotlinc`, `tsc --noEmit`).
*Closes:* non-existent method/property/import/argument.

### Ask the system, not the config · `process`
Before running tests, print the effective `DB_CONNECTION`/`DB_DATABASE` from the process that will run them (`docker exec <ctr> php -r 'echo config("database.default");'`) and compare with the expected value. Before using an image for tests, run `docker run <image> python -c 'import pytest'`. For fixtures, read their code before expecting a result. Take expected API statuses from the contract (201), not memory.
*Closes:* wrong assumption about environment, fixture or format.

## Checklist before acting
- [ ] Printed the real shape (`type()`, keys, `.schema`, migration) before writing the reader or query?
- [ ] Is every field, enum and bound taken from the contract file or the source, not from memory?
- [ ] Is every method/import found with `rg` or in docs, and does a single-file compile pass?
- [ ] Did I ask the live process which database/environment it uses, instead of trusting config files?
- [ ] Does this routine (rules index, subnet check, log read) already have a shared script?
