# AXIOM-Bench 0.1 Conformance Runner Contract

Status: proposed normative M1 runner contract  
Owning milestone: M1 / issue #12  
Companion: `AXIOM_BENCH_SPEC.md`

## 1. Purpose

The provider-free conformance runner proves that AXIOM-Bench can:

- assemble a clean task workspace;
- apply an exact repository-controlled reference or seeded-wrong candidate;
- execute frozen argument-array commands;
- enforce reliability budgets;
- separate public, acceptance, and security outcomes;
- retain raw and canonical Evidence;
- replay a result without a model or subprocess;
- reject tampering and untrusted local execution.

It does not score a model and does not make the benchmark suite complete.

## 2. Supported adapters

```text
reference
seeded_wrong
replay
```

`reference` and `seeded_wrong` use trust classes `trusted_reference` and
`trusted_seeded_wrong`. They may run only repository-controlled files.

`replay` uses `replay_only` and executes no candidate or command.

No adapter in this capability accepts `untrusted_model_output`.

## 3. Task input

The runner consumes one schema-valid task document and one selected language
variant. The variant must declare:

- `candidate_path` inside the workspace;
- starter file path;
- reference solution path;
- at least one seeded-wrong path;
- formatter, check, public-test, acceptance-test, and optional security-test
  argument arrays;
- expected entry point and declared dependencies.

M1 v0.7 conformance supports one candidate source file per task variant. Multi-
file candidate editing remains a later runner extension and requires a schema
version change or an explicit compatible extension.

## 4. Command placeholders

Command arguments are expanded independently. Shell parsing is forbidden.

Supported exact placeholders inside an argument:

```text
{python}
{workspace}
{task_root}
{candidate}
{language}
```

A placeholder may occupy an entire argument or appear within one argument. The
expanded value remains one subprocess argument.

Unknown or malformed `{...}` placeholders are rejected before process start.
No environment-variable, tilde, glob, command-substitution, redirection, pipe,
or quote interpretation is performed.

## 5. Workspace law

For each conformance run:

1. create a new temporary workspace;
2. validate task and candidate paths;
3. reject absolute paths, backslashes, `.`/`..`, path escapes, and symbolic
   links;
4. copy the starter bytes to `candidate_path`;
5. copy the exact selected reference/seeded-wrong bytes over `candidate_path`;
6. verify candidate file count, bytes, and changed-line budgets;
7. run commands with the workspace as `cwd`;
8. copy all retained Evidence to the output bundle;
9. remove the temporary workspace.

No repository source or benchmark control file is writable through the task
candidate allowlist.

## 6. Environment law

The child receives a minimal explicit environment:

- `PATH` when present;
- Windows runtime variables required to start a process when present;
- temporary-directory variables pointing into the workspace;
- `HOME` pointing into the workspace;
- `LANG=C.UTF-8`;
- `LC_ALL=C.UTF-8`;
- `TZ=UTC`;
- `PYTHONHASHSEED=0`.

The exact key/value mapping is recorded in the command record. Secrets,
credentials, provider keys, repository tokens, proxy variables, and undeclared
task variables are not inherited.

## 7. Command order and stopping

Commands execute in this order:

```text
format
check
public_test
acceptance_test
security_test (only when declared)
```

The runner stops at the first failed phase.

Failure mapping:

```text
format -> format_failure
check -> compile_failure
public_test -> public_test_failure
acceptance_test -> acceptance_test_failure
security_test -> security_failure
command timeout -> timeout
combined retained output limit -> resource_limit
workspace/candidate rule -> invalid_patch or forbidden_file
executor internal failure -> runner_error
```

A check success provides both parse and compile success in the provider-neutral
conformance layer. Language-specific adapters may later expose finer-grained
facts without changing full-success semantics.

## 8. Bounded output

Stdout and stderr are read concurrently as bytes. The combined retained-output
cap applies across both streams.

When the cap is exceeded:

- only the exact bounded prefixes are retained;
- `output_limited` becomes true;
- the child is terminated, then killed if needed, and reaped;
- the command and attempt fail with `resource_limit`;
- no later phase runs.

This is a retained-output reliability control, not host isolation.

## 9. Timeout and termination

Each command has the task's frozen command timeout. On timeout the runner:

1. records the timeout signal;
2. requests termination;
3. waits a short fixed grace period;
4. kills the child if still live;
5. reaps it;
6. records final return code and termination method;
7. fails the attempt with `timeout`.

POSIX session creation may help terminate the trusted fixture's immediate
process group. It is not represented as complete descendant containment.

## 10. Evidence layout

A conformance output directory contains:

```text
raw/
  candidate.bin
  trace.jsonl
  commands/*.json
  stdout/*.bin
  stderr/*.bin
canonical/
  attempt.json
  conformance-report.json
  trace.jsonl
  commands/*.json
  stdout/*.bin
  stderr/*.bin
bundle-manifest.json
AXIOM_BENCH_CONFORMANCE.zip
```

Raw records retain real timestamps and durations. Canonical records normalize
only declared volatile fields:

- timestamps -> `1970-01-01T00:00:00Z`;
- durations/wall-clock -> `0`;
- temporary absolute paths -> stable placeholders.

Candidate bytes, command arguments after stable path normalization, outputs,
exit codes, timeout/output-limit facts, outcomes, failure reasons, hashes, and
score decisions are not normalized away.

## 11. Conformance decision

Reference adapter passes conformance only when the attempt has full success.

Seeded-wrong adapter passes conformance only when:

- full success is false;
- the actual failure reason equals the task's
  `required_failure_for_seeded_wrong`;
- evidence is complete.

A wrong fixture that unexpectedly succeeds is a harness/task failure, not a
successful model result.

## 12. Replay law

Replay reads a canonical conformance ZIP and:

- rejects duplicate ZIP paths, backslashes, absolute paths, `..`, symlinks, and
  oversized entry/count limits;
- verifies every manifest file hash and size;
- validates attempt, command, report, and trace schemas;
- checks monotonically increasing trace sequence numbers;
- checks command-record references and hashes;
- recomputes full-success and conformance decisions;
- verifies the bundle semantic hash;
- executes no subprocess and writes no candidate workspace.

A replayed decision must equal the recorded decision. Any mismatch is
`AX-BENCH-REPLAY-TAMPERED`.

## 13. Deterministic bundle

Canonical bundle entries use:

- sorted POSIX paths;
- fixed ZIP timestamp;
- fixed regular-file permissions;
- deterministic compression settings;
- canonical JSON;
- no raw volatile records.

Two successful runs of the same trusted fixture on the same frozen toolchain
must produce byte-identical canonical ZIPs. Raw Evidence may differ in timing.

## 14. Stable runner findings

The runner reserves stable categories including:

```text
AX-BENCH-RUNNER-INVALID-TASK
AX-BENCH-RUNNER-INVALID-PATH
AX-BENCH-RUNNER-SYMLINK
AX-BENCH-RUNNER-UNKNOWN-PLACEHOLDER
AX-BENCH-RUNNER-FORBIDDEN-FILE
AX-BENCH-RUNNER-BUDGET
AX-BENCH-RUNNER-TIMEOUT
AX-BENCH-RUNNER-OUTPUT-LIMIT
AX-BENCH-RUNNER-CONFORMANCE
AX-BENCH-SANDBOX-REQUIRED
AX-BENCH-REPLAY-TAMPERED
```

Exact machine-readable reports carry code, path/phase, and message.

## 15. Explicit non-goals

This capability does not provide:

- live model calls;
- untrusted candidate extraction or execution;
- Docker/VM/cloud sandbox implementation;
- a frozen benchmark suite;
- real AXIOM/Rust/Zig/Go task variants;
- compiler installation;
- process CPU/memory/syscall/network quotas;
- multi-file full-agent editing;
- statistical analysis;
- AI-first superiority evidence.
