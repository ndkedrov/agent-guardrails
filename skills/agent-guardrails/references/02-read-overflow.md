# 02 · Read Output Overflow

> In nearly every incident the tool truncated the output because one call asked for more than the output limit allows, so the agent had to read the missing part again. It is a habit, not a one-off: in about a sixth of the records the agent says it had done the same thing before. Self-promises to "read narrowly" do not last, so mechanical limiters are needed. **Share:** 190 of 1,156 recorded incidents (16.4%).

## What goes wrong
- **Combined read of rules, documents and code in one call with too small a limit** (135) — several rule files, handoffs, contracts or source files are concatenated in one command (typically at session start or after a context reset) with a total output limit below their combined size. The middle or end is cut off and re-read separately; some rules cannot honestly be counted as read. Most records involve rules or instructions.
- **Whole JSON, registry, receipt or hash map printed instead of the needed fields** (28) — to check one entry, the agent prints a whole one-line registry, a full JSON proof, every key/hash of a large dictionary, or a database row including a binary video header. Causes: `rg` on a single-line file, `cat`, a `status` command that ignores `--id`, a formatter that truncates nested collections but not the top-level map.
- **Search, listing or index that is too broad and unfiltered** (27) — `git status` without paths (hundreds of lines), recursive search through a temp or build directory, `grep` over a large log (tens of thousands of tokens), printing a memory or archive index of all projects instead of one entry, or a full diff including tests and config.

Often co-occurs: guessed file names and directories, numbered files without the leading zero, globs with no matches, Python heredocs with non-ASCII text failing without UTF-8, and lease/wrapper tools called without an absolute path or with `--help` as an argument.

## Why it happens
- Two limits are confused: the agent raises the limit of the inner command but not the overall output limit of the outer tool, or sets limits by eye instead of from a measured size.
- File size is not checked before reading; nobody knows whether four rule files fit in one call.
- The startup sequence (context recovery, "read the rules") by design requires many large files, and the agent reads them as a batch instead of via an index or digest. Most incidents sit at the start of a segment or after context compaction.
- Tools return everything by default: `rg` on a one-line JSON prints the whole line, `status` ignores `--id`, `git status` is not path-limited, one memory index serves all projects.
- The agent prints structure instead of a summary: keys and hashes instead of counts; top-level maps are not abbreviated.
- Paths and file names are guessed by analogy with other projects instead of taken from an index or `ls`.
- Self-suggestion fails: the agent already wrote "from now on I read narrowly" and repeated the mistake in the same or the next session.

## What it costs
- Truncated output means part of the rules or contracts was never read; ranges must be re-read, duplicating tool calls and context.
- An unread part cannot count as evidence; agents must explicitly decline to count it as read, and review or verification is delayed.
- Wasted context: more than 20k tokens from one `rg` over a registry, 30k from a diagnostic JSON, about 28k from a log grep.
- Foreign data enters the context: other agents' registry entries, other projects' details from an archive index.
- Segment budget spent on recovery; registration of a new executor delayed. No risk to product code or data was recorded: nothing changed in any of these incidents.

## How to prevent it
### Budgeted read wrapper (`ctxread`) · `script`
`ctxread <file[:from-to]>...` computes the total size before printing. If the sum exceeds ~12,000 characters, it prints per file only the size, headings (`^#`) and a hint with exact line ranges, instead of silently truncating.
**Rule:**
> Rules, contracts and code are read only through `ctxread`. Direct `cat`/`sed -n` over several files in one call is forbidden. First `wc -c`, then read no more than ~12,000 characters per call.

*Closes:* combined read of rules, documents and code.

### Pre-tool hook against "fat" read commands · `hook`
Block a Bash call when: (a) `cat`/`sed -n`/`head` target 3 or more files without an overall `| head -c N`; (b) `rg`/`grep` run over registry or receipt `*.json` without `-o`, `-l`, `-m`, `--max-columns` or `| jq`; (c) `git status` has no `--short -- <paths>` or `| head`; (d) `find`/`ls -R` target a temp directory, `DerivedData` or `build`. The hook reply must contain a ready safe command template so the agent does not guess.
*Closes:* all three counted subtypes.

### Narrow rules digest for start and recovery · `template/validator`
Generate `RULES_DIGEST.md` (up to ~4,000 characters: numbered rules in 1–2 lines each plus paths of the full sections).
**Rule:**
> At session start or after context recovery read only `RULES_DIGEST.md` and the section it points to, by line range. Do not read full rule files whole.

Split big rule files into sections of at most 150 lines, each listed in an index.
*Closes:* combined read of rules, documents and code.

### One wrapper for JSON proofs and registries (`jshow`) · `script`
`jshow <file> --path 'agents[id=X]' --fields a,b,c` prints only named fields and replaces any map or array with more than 10 elements by `<N items>`. Fix the `status` command so `--id` really filters.
**Rule:**
> Registries, receipts and JSON proofs are never read with `cat`, `rg` or by printing a whole object; only `jshow` or `jq` with an explicit field list. For hash dictionaries print `len(...)`, not the keys.

*Closes:* whole JSON/registry/hash-map output.

### One output budget per call · `rule`
**Rule:**
> The outer tool's output limit is the budget of the whole call, not of one command; the sum of all parts must stay below it. If the size is unknown, run `wc -c` in a separate call first. Truncated output counts as unread, and repeating the same request size is forbidden: the next call must be at least half as wide.

*Closes:* combined read; whole JSON output.

### Machine path index instead of guessing · `script`
Generate `paths.index` (output of `rg --files` over the project and the rule directories).
**Rule:**
> Before reading or searching by file name, check it in `paths.index` or with `rg --files | rg <name>`; do not assume numbering (`06`, not `6`) or the presence of directories.

Extend the hook so that `Read`/`rg` on a path absent from the index returns the nearest matches instead of "No such file".
*Closes:* related guessed paths and file names.

### Per-project memory index and a trap-free environment · `script`
Split the memory index into one file per project and add `memory_lookup <project>` that prints only the current project's entries. Set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` in the agent environment, and put lease/wrapper tools on PATH through an absolute-path shim.
*Closes:* overly broad index; related encoding and PATH problems.

### Repeat-offence guard for the shared mistake log · `process`
If an agent reports the same class of mistake ("truncated output") a second time in a session, the orchestrator does not accept the promise "I will read narrowly from now on"; it makes `ctxread` and the first hook mandatory in the brief of the next agent. Repeated "again" records show an agent's memory of its own mistake does not work.
*Closes:* all subtypes.

## Checklist before acting
- [ ] I measured size first (`wc -c` / `wc -l`) and the planned output is under the call's total limit.
- [ ] I am reading one file or one line range, not concatenating several files.
- [ ] For JSON and registries I use `jq` / `jshow` with explicit fields, never the whole object.
- [ ] `git status`, `rg`, `grep`, `find` are scoped to paths, with `--short`, `-m`, `-l` or `| head`.
- [ ] If the last output was truncated, my next call is at least half as wide, and the truncated part is not counted as read.
- [ ] File names come from an index or listing, with numbering and leading zeros as written.
