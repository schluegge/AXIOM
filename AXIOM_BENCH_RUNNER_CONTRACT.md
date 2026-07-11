# AXIOM-Bench 0.1 Trusted Conformance Runner Contract

Status: implemented M1 normative contract  
Owning milestone: M1 / issue #12  
Companion: `AXIOM_BENCH_SPEC.md`

## 1. Purpose

The trusted conformance layer proves that the benchmark harness can execute
repository-controlled reference and seeded-wrong candidates, retain complete
Evidence, build deterministic canonical bundles, and replay decisions without a
model or subprocess.

It does not score a model, isolate malicious code, freeze the benchmark suite,
or compare language quality.

## 2. Trust boundary

Supported execution adapters:

```text
reference     -> trusted_reference
seeded_wrong  -> trusted_seeded_wrong
```

Replay uses `replay_only` and starts no process.

`untrusted_model_output` is rejected before candidate application with:

```text
AX-BENCH-SANDBOX-REQUIRED
```

The executor is a reliability-controlled local process runner, not a sandbox.
Trusted commands may access resources available to the host account. This
capability does not claim filesystem namespaces, syscall filtering, network
isolation, CPU/memory quotas, or malicious process-tree containment.

## 3. Task input

The runner consumes one schema-valid task and one selected language variant.
The runner-compatible variant must additionally declare `candidate_path`.

Required runner fields include:

- one candidate path present in `candidate_edit_allowlist`;
- starter, reference, and seeded-wrong source paths;
- formatter, check, public-test, acceptance-test, and optional security-test
  argument arrays;
- reliability budgets;
- expected seeded-wrong failure reason.

M1 trusted conformance applies exactly one candidate source file. The
`max_candidate_files` budget must permit that file. Multi-file candidate editing
requires a later compatible extension or schema version.

## 4. Paths

All contract, bundle, and internal-reference paths must be exact normalized
POSIX relative paths.

Rejected forms include:

- absolute paths;
- backslashes;
- empty, `.` or `..` components;
- noncanonical repeated separators;
- Windows drive or alternate-stream separators;
- root escapes;
- symbolic links where prohibited;
- case-folded or Unicode-normalized ZIP collisions.

Task source paths must remain under the task root. Candidate paths must remain
under the temporary workspace. Replay paths must remain under the extracted
bundle root.

## 5. Output directory

The caller must provide a path that does not already exist. The runner creates
that directory but never recursively replaces an existing directory.

The output directory may not be inside the repository or task root. Creation or
initial Evidence-write failure is returned as a structured
`AX-BENCH-RUNNER-INVALID-PATH` finding rather than an unhandled filesystem
exception.

## 6. Candidate application

For each run the runner:

1. validates the task and selected adapter;
2. validates source and candidate paths;
3. reads the exact starter and selected candidate bytes;
4. checks candidate-byte and changed-line budgets;
5. creates a new temporary workspace;
6. writes the starter and then selected candidate to `candidate_path`;
7. executes the frozen phase commands;
8. copies retained Evidence outside the temporary workspace;
9. removes the temporary workspace.

The candidate application surface is one declared file. The local child remains
trusted; this capability does not claim complete observation or prevention of
all other host filesystem accesses.

## 7. Command expansion

Commands are arrays. Each array item remains one subprocess argument.
`shell=False` is mandatory.

Supported placeholders are:

```text
{python}
{workspace}
{task_root}
{candidate}
{language}
```

Unknown, malformed, or unresolved placeholders are rejected before process
start. No shell quotes, variables, globbing, pipes, redirection, command
substitution, or tilde expansion are interpreted.

## 8. Environment

The child receives an explicit minimal mapping containing only available process
startup variables plus workspace-local temporary and home paths:

```text
PATH
SYSTEMROOT / WINDIR / PATHEXT / COMSPEC when present
HOME
TEMP / TMP / TMPDIR
LANG=C.UTF-8
LC_ALL=C.UTF-8
TZ=UTC
PYTHONHASHSEED=0
```

Provider keys, repository tokens, proxy variables, seeded secrets, and other
inherited variables are omitted. The exact mapping is retained in each command
record.

## 9. Phase order

Commands execute in this order and stop on the first failure:

```text
format
check
public_test
acceptance_test
security_test when declared
```

Failure mapping:

```text
format          -> format_failure
check           -> compile_failure
public_test     -> public_test_failure
acceptance_test -> acceptance_test_failure
security_test   -> security_failure
process start   -> runner_error
command/task timeout -> timeout
output/feedback/invocation budget -> resource_limit
```

A successful provider-neutral check records parse and compile success together.

## 10. Reliability budgets

The trusted runner enforces:

- maximum candidate bytes;
- maximum changed lines;
- the single-file candidate capability;
- maximum command/compiler invocation count;
- per-command timeout;
- total-task timeout;
- combined retained stdout/stderr bytes per command;
- cumulative canonical feedback bytes across commands.

Token, iteration, and tool-call fields are retained for later model adapters but
are not consumed by the provider-free trusted adapters.

On timeout or output overflow, the child is terminated, killed if necessary,
and reaped. POSIX process-group handling is best effort and not represented as
complete descendant containment.

A process that cannot start produces a command record with:

```text
termination = not_started
return_code = null
failure_reason = runner_error
```

## 11. Evidence

The output directory contains:

```text
raw/
  candidate.bin
  attempt.json
  conformance-report.json
  trace.jsonl
  commands/*.json
  stdout/*.bin
  stderr/*.bin
canonical/
  candidate.bin
  attempt.json
  conformance-report.json
  trace.jsonl
  commands/*.json
  stdout/*.bin
  stderr/*.bin
  bundle-manifest.json
conformance-report.json
AXIOM_BENCH_CONFORMANCE.zip
```

The ZIP contains the complete `canonical/` file set at its root. The external
report additionally records the final ZIP SHA-256.

Raw Evidence keeps real timestamps, durations, absolute temporary paths, and
original stdout/stderr bytes. Canonical Evidence normalizes only declared
volatile data:

- timestamps to `1970-01-01T00:00:00Z`;
- durations and wall-clock usage to zero;
- temporary workspace and task-root strings in metadata, trace payloads, and
  stdout/stderr bytes to stable placeholders.

Candidate bytes, non-path output content, exit status, timeout/limit facts,
outcomes, failure reason, and hashes of the resulting canonical payloads are not
normalized away.

## 12. Conformance decision

Reference conformance passes only when the attempt has complete Evidence and full
success.

Seeded-wrong conformance passes only when:

- full success is false;
- Evidence is complete;
- the actual failure reason exactly equals
  `required_failure_for_seeded_wrong`.

A wrong candidate that succeeds is a harness failure, not a successful result.

## 13. Deterministic bundle

Canonical ZIPs use sorted paths, fixed timestamps, fixed regular-file
permissions, canonical JSON, deterministic compression settings, stable
placeholder substitution, and no raw volatile records.

Two runs of the same trusted fixture under the same frozen effective toolchain
must produce byte-identical canonical ZIPs, including when a command emits the
temporary workspace or task-root path.

## 14. Replay

Replay:

- starts zero subprocesses;
- rejects unsafe, duplicate, colliding, encrypted, symlink, or over-count ZIP
  entries;
- enforces both declared ZIP sizes and actual streamed decompressed entry/total
  byte limits;
- converts malformed archives and memory exhaustion into a failed replay report;
- validates manifest, attempt, command, report, trace, and replay schemas;
- safely resolves every path read from internal JSON;
- verifies the exact archive file set;
- verifies file hashes and sizes;
- verifies manifest semantic identity;
- verifies task, language, adapter, attempt, trace, command, and stream links;
- verifies actual candidate bytes against retained candidate hashes;
- verifies trace sequence numbers;
- derives phase outcomes and the first failure from retained command/stream
  Evidence and budgets;
- requires attempt, report, check-result trace, and score-decision trace values
  to agree with the replay-derived decision.

Any malformed or inconsistent bundle fails with
`AX-BENCH-REPLAY-TAMPERED`.

## 15. Findings

Stable categories include:

```text
AX-BENCH-RUNNER-INVALID-TASK
AX-BENCH-RUNNER-INVALID-PATH
AX-BENCH-RUNNER-SYMLINK
AX-BENCH-RUNNER-UNKNOWN-PLACEHOLDER
AX-BENCH-RUNNER-FORBIDDEN-FILE
AX-BENCH-RUNNER-BUDGET
AX-BENCH-RUNNER-CONFORMANCE
AX-BENCH-SANDBOX-REQUIRED
AX-BENCH-REPLAY-TAMPERED
```

Machine-readable findings contain code, path or phase, and message. Attempt and
conformance-report documents share one exact failure-reason vocabulary.

## 16. Explicit non-goals

This capability does not provide:

- live model calls or candidate extraction;
- safe execution of model-generated code;
- Docker, VM, cloud, or Inspect sandbox implementation;
- real AXIOM/Rust/Zig/Go language tasks;
- frozen language packs or toolchains;
- compiler installation;
- operating-system CPU, memory, syscall, disk, or network quotas;
- complete host filesystem mutation confinement;
- cryptographic authenticity against an attacker who can consistently rewrite
  every semantic document and hash without an external signature or
  transparency anchor;
- multi-file full-agent editing;
- statistical analysis or AI-first superiority evidence.
