# 13 · Secrets in tool output

> In every one of these incidents the agent read a config, log, or test file whole (cat, sed, or grep with no filter) and so printed sensitive values into the tool result: a signing team identifier, store-backend identifiers, database passwords and connection details, test tokens, participant codes, a pairing code. None involved a private key or a live production token, but in all cases the protection was only after the fact: the agent noted that it would not repeat the value and promised to filter next time. In two cases the task itself said not to show such values, and they were shown anyway. **Share:** 13 of 1,156 recorded incidents (1.1%).

## What goes wrong
- **Full dump of a build/release config containing signing or store identifiers** (5) — for one or two needed fields (a build number, a path) the agent printed a whole project YAML, a service file, or a search result from release notes, exposing a signing team identifier or store-backend identifiers.
- **Docker config and server logs read with credentials inside** (3) — too wide a range of a Docker configuration (database passwords, test database details) or the head of a server log with an old pairing code, where only container names, paths, or specific lines were needed.
- **Search or structure dump of a private test-credentials file with an incomplete deny list** (2) — grep over a private file of test access, or printing the structure of an old test config while forbidding only some field names, leaked local test tokens, addresses, and participant codes.
- **Whole JSON object or process arguments instead of aggregates** (3) — instead of the permitted fields or counts the agent printed an entire historical report, a whole request object from UI-verification evidence, or a full resource list with build-process arguments, exposing internal identifiers, credential identifiers, and a loyalty-card code.

## Why it happens
- The default move is to read the whole file (cat, sed, full JSON/YAML) and select afterwards; the filter lands after the value is already in the tool result.
- Protection rests on the agent's memory and on a deny list: "do not show X" holds only while remembered, an incomplete list of forbidden field names let tokens and codes through, and an explicit ban in the task did not stop the output.
- Sensitive values sit in ordinary files the agent reads for other reasons (project config, Docker config, working notes, test config, server logs); secrets are not separated from the data needed for the work.
- Side channels: searching text notes, process arguments in resource listings, a path that does not exist followed by a broad re-read after the error all produced even more output.
- There is no mechanical check on output after a call: the tool does not mask secrets, and the agent learns of the leak from the result itself.

## What it costs
- Signing identifiers, store-backend identifiers, database passwords and connection details, test tokens, a pairing code, and a loyalty-card code ended up in the tool log and the session history.
- Database passwords were printed during a diagnosis where production was explicitly off limits.
- In one case the output had to be stopped and the owner told separately about the exposure.
- An explicit instruction to hide identifiers was violated, which lowers trust in the agent's compliance with restrictions.
- Several incidents also involved wasted work first: truncated output, repeated batch reads, a path error.
- Values were not confirmed as production in some cases, but for database credentials the risk to data stood until verified.

## How to prevent it
### A safe config reader instead of cat/sed · `script`
`safe-read <file> [field...]` on the agents' PATH: for YAML/JSON/.env/Docker configs it prints only keys and values from an allowlist (build number, version, service and container names, paths) and masks every other value as `***`. With no arguments it prints only key names. Keep the field lists in one file in the project repo; the default mode is deny.
*Closes:* all subtypes, above all the first two.

### PreToolUse hook: block direct reads of sensitive files · `hook`
Before Bash/Read, inspect the command and path. If it is `cat`/`sed`/`head`/`tail`/`grep`/`rg`/`less`/`awk`, `docker compose config`, `docker inspect`, `ps`/`pgrep -fl`, or `env`/`printenv` against `project.yml`, `*.xcconfig`, `.env*`, `docker-compose*.yml`, the private test-credentials file, working notes, server `*.log`, or JSON evidence reports, block with the message "use `safe-read`; print only allowed fields". Keep the pattern list in one place and extend it after each new incident.
*Closes:* subtypes 1-4.

### Allowlist of fields, not a deny list · `rule`
> **Rule:** Sensitive files (project config, `.env*`, docker-compose files, test-credential files, server logs, evidence reports, build-process lists) are NOT read whole and NOT printed. Read them only through `safe-read` with an explicit list of needed fields; a field not on the list is not printed. The ban on signing identifiers, store-backend identifiers, tokens, passwords, pairing codes, and participant codes holds even when the task does not mention it. If a needed value is unknown, ask instead of dumping the file.

*Closes:* subtypes 1 and 3 (incomplete deny list).

### Output to a file, aggregates only · `rule`
> **Rule:** Do not print large JSON, reports, or resource and process lists. First `cmd > <scratchpad>/out.json`, then extract only the needed numbers/fields with `jq` or python using an explicit key list (`jq '{ok,count,build}' out.json`). For process arguments print only PID and name, never the command line (`ps -o pid=,comm=`).

*Closes:* subtype 4 (and logs in subtype 2).

### Keep secrets out of the configs read for work · `process`
Move signing identifiers, store-backend identifiers, database passwords, and test tokens out of project config, Docker configs, and working notes into a git-ignored `.env` or xcconfig that is substituted at build time; leave only variable names in the configs. In Docker use `env_file` or secrets rather than values in the compose file. Issue agents separate, short-lived test credentials that differ from the credentials of any database holding real data.
*Closes:* subtypes 1-3.

### Scanner on tool output after the call · `hook`
PostToolUse for Bash/Read: scan the result for patterns (a 10-character team identifier next to `DEVELOPMENT_TEAM`, `password=`, `token=`, `PAIRING`, credential UUIDs, values from the test-credentials file). On a match do not stay silent: write to an incident log and return "a secret reached the output: do not repeat it, tell the owner, propose rotation". This does not remove the value from history, so it is a signal and a counter, not the main defence.
*Closes:* all subtypes (detection).

### Read server logs only through a filter · `rule`
> **Rule:** Read server and application logs only as `grep -E '<needed pattern>' | tail -n 40`; never print the start of a file (`head`, `cat`), where pairing codes and tokens appear. For pairing/disconnect diagnostics search only for lines with event names.

*Closes:* subtype 2.

### Check that the path exists before reading · `script`
Before reading a plan or config run `ls` / `test -f` on the exact path (or `git ls-files | rg <name>`), and only then call `safe-read`. This removes the chain "path error, broad re-read, extra output".
*Closes:* subtype 1.

## Checklist before acting
- [ ] I need specific fields; I named them before opening the file.
- [ ] The file is read through `safe-read` or a field-selecting `jq`, never `cat`/`sed` whole.
- [ ] I confirmed the path exists (`ls`/`test -f`) so an error cannot trigger a broad re-read.
- [ ] Large JSON or process lists go to a file first; I print only counts and allowed keys.
- [ ] Logs are read with `grep` plus `tail`, not from the head.
- [ ] If a secret reached the output anyway: I do not repeat it, I tell the owner, and I suggest rotation.
