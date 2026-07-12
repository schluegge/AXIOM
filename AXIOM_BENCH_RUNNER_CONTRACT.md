# AXIOM-Bench 0.1 Trusted Conformance Runner Contract

Status: implemented M1 normative contract  
Owning milestone: M1 / issue #12  
Companion: `AXIOM_BENCH_SPEC.md`

## 1. Purpose

The trusted conformance layer proves that the benchmark harness can execute
repository-registered reference and seeded-wrong candidates, retain complete
Evidence, build deterministic canonical bundles, and replay decisions without a
model or subprocess.

It does not score a model, isolate malicious code, freeze the benchmark suite,
or compare language quality.

## 2. Supported interface and trust boundary

The supported authority-enforcing interfaces are:

- exports from the `axiom_bench` package;
- `tools/run_benchmark_conformance.py`;
- `tools/replay_benchmark_conformance.py`;
- `run_repo_proof.py`.

`axiom_bench.runner` and `axiom_bench.replay` contain implementation helpers and
are not a second supported security interface.

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

## 3. Trusted task authority

The local trusted-task authority is:

```text
benchmarks/contracts/0.1.0/trusted-tasks.json
```

Before output creation, workspace creation, candidate application, or process
start, the supported runner interface must:

1. load the registry and its exact local schema;
2. reject duplicate task IDs or paths;
3. resolve the declared task path as exact normalized POSIX repository-relative
   syntax;
4. reject root escapes and symbolic links;
5. require a regular task file;
6. validate the task with the canonical task schema;
7. require registry and task-document IDs to agree;
8. compute the task SHA-256 from the registered repository bytes;
9. require the caller-supplied path to equal the registered resolved path.

A copied, modified at another path, or otherwise unregistered task must fail
before any output directory or process exists with:

```text
AX-BENCH-RUNNER-UNTRUSTED-TASK
```

Authority file or schema failures use `AX-BENCH-RUNNER-AUTHORITY`.

## 4. Task input

After authority resolution, the runner consumes the registered schema-valid task
and one selected language variant. The runner-compatible variant must declare
`candidate_path`.

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

## 5. Paths

All contract, registry, bundle, and internal-reference paths must be exact
normalized POSIX relative paths.

Rejected forms include:

- absolute paths;
- backslashes;
- empty, `.` or `..` components;
- noncanonical repeated separators;
- Windows drive or alternate-stream separators;
- root escapes;
- symbolic links where prohibited;
- case-folded or Unicode-normalized ZIP collisions.

Task source paths remain under the registered task root. Candidate paths remain
under the temporary workspace. Replay paths remain under the extracted bundle
root.

## 6. Output directory

The caller must provide a path that does not already exist. The runner creates
that directory but never recursively replaces an existing directory.

The output directory may not be inside the repository or task root. Creation or
initial Evidence-write failure is returned as a structured
`AX-BENCH-RUNNER-INVALID-PATH` finding rather than an unhandled filesystem
exception.

## 7. Candidate application

For each run the supported runner interface:

1. resolves and validates repository task authority;
2. validates the selected adapter and language variant;
3. validates source and candidate paths;
4. reads the exact starter and selected candidate bytes;
5. checks candidate-byte and changed-line budgets;
6. creates a new temporary workspace;
7. writes the starter and then selected candidate to `candidate_path`;
8. executes the frozen phase commands;
9. copies retained Evidence outside the temporary workspace;
10. removes the temporary workspace.

The candidate application surface is one declared file. The local child remains
trusted; this capability does not claim complete observation or prevention of
all other host filesystem accesses.

## 8. Command expansion

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

## 9. Environment

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

## 10. Phase order and failure mapping

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

## 11. Reliability budgets

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

## 12. Evidence

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

## 13. Authoritative conformance decision

Reference conformance expects complete Evidence and full success with no failure
reason.

Seeded-wrong conformance expects incomplete success and the exact
`required_failure_for_seeded_wrong` from the registered task acceptance
contract.

The adapter and registered task derive these expectations. A stored
`expected_outcome` is Evidence to cross-check, not authority.

A wrong candidate that succeeds is a harness failure, not a successful result.

## 14. Deterministic bundle

Canonical ZIPs use sorted paths, fixed timestamps, fixed regular-file
permissions, canonical JSON, deterministic compression settings, stable
placeholder substitution, and no raw volatile records.

Two runs of the same registered fixture under the same frozen effective
toolchain must produce byte-identical canonical ZIPs, including when a command
emits the temporary workspace or task-root path.

## 15. Replay

Replay has two gates.

### 15.1 Internal consistency gate

Replay:

- starts zero subprocesses;
- rejects unsafe, duplicate, colliding, encrypted, symlink, or over-count ZIP
  entries;
- enforces declared and actual streamed decompressed size limits;
- converts malformed archives and memory exhaustion into a failed report;
- validates manifest, attempt, command, report, trace, and replay schemas;
- safely resolves every internal path;
- verifies the exact archive file set, hashes, sizes, semantic manifest identity,
  candidate bytes, command streams, trace sequence, outcomes, and limits;
- derives phase outcomes and the first failure from retained command/stream
  Evidence and budgets;
- requires attempt, report, check-result trace, and score-decision trace values to
  agree with the replay-derived result.

Malformed or internally inconsistent bundles fail with
`AX-BENCH-REPLAY-TAMPERED`.

### 15.2 Repository authority gate

Only after internal replay passes, replay must:

1. resolve `task_id` in the repository trusted-task registry;
2. compare `task_sha256` with the registered task bytes;
3. require the selected language variant to exist in that task;
4. derive trust class from the adapter;
5. derive expected success/failure from adapter and registered task acceptance;
6. reject report or attempt disagreement.

Authority disagreement fails with:

```text
AX-BENCH-REPLAY-AUTHORITY
```

This gate specifically rejects coherent bundle rewrites where an attacker
repairs the manifest and internal hash chain but changes the registered task
hash or relabels seeded-wrong Evidence as reference Evidence.

## 16. Findings

Stable categories include:

```text
AX-BENCH-RUNNER-UNTRUSTED-TASK
AX-BENCH-RUNNER-AUTHORITY
AX-BENCH-RUNNER-INVALID-TASK
AX-BENCH-RUNNER-INVALID-PATH
AX-BENCH-RUNNER-SYMLINK
AX-BENCH-RUNNER-UNKNOWN-PLACEHOLDER
AX-BENCH-RUNNER-FORBIDDEN-FILE
AX-BENCH-RUNNER-BUDGET
AX-BENCH-RUNNER-CONFORMANCE
AX-BENCH-SANDBOX-REQUIRED
AX-BENCH-REPLAY-TAMPERED
AX-BENCH-REPLAY-AUTHORITY
```

Machine-readable findings contain code, path or phase, and message. Attempt and
conformance-report documents share one exact failure-reason vocabulary.

## 17. Explicit non-goals

This capability does not provide:

- live model calls or candidate extraction;
- safe execution of model-generated code;
- Docker, VM, cloud, or Inspect sandbox implementation;
- real AXIOM/Rust/Zig/Go language tasks;
- frozen language packs or toolchains;
- compiler installation;
- operating-system CPU, memory, syscall, disk, or network quotas;
- complete host filesystem mutation confinement;
- protection when the attacker can also rewrite the trusted repository registry
  or replace the expected repository checkout without an external signature or
  transparency anchor;
- multi-file full-agent editing;
- statistical analysis or AI-first superiority evidence.
