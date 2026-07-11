# M1 Conformance Runner Source Evidence

Status: authoritative implementation evidence for the provider-free M1 runner  
Applies to: issue #12  
Python baseline: 3.11

## Resolved Context7 source

```text
/python/cpython/v3.11.14
```

The selected source is the official CPython 3.11 standard-library documentation
and source tree.

## Captured subprocess contracts

AXIOM-Bench uses `subprocess.Popen` with an argument sequence and `shell=False`.
The runner does not construct a shell command string.

Relevant contracts:

- an argument sequence allows Python to preserve argument boundaries;
- `cwd` changes the child working directory before execution;
- an explicit `env` mapping replaces inherited environment variables;
- `stdout=PIPE` and `stderr=PIPE` expose byte streams;
- `poll()`, `wait()`, `terminate()`, and `kill()` provide process lifecycle
  controls;
- timeout handling must terminate/kill and then reap the process;
- `communicate()` avoids pipe deadlocks, but its in-memory buffering is not
  suitable for AXIOM-Bench's explicit retained-output cap;
- `start_new_session=True` creates a new POSIX session but is not a security
  boundary and is not a complete cross-platform process-tree sandbox;
- on Windows, creation flags and child termination behavior differ;
- `shell=False` avoids shell interpretation but does not make an untrusted
  executable or generated program safe.

Implementation decision:

- command arrays only;
- no shell expansion, redirection, pipelines, or command substitution;
- explicit working directory inside a disposable workspace;
- minimal deterministic environment allowlist;
- concurrent bounded byte-stream readers;
- timeout and retained-output limit terminate the child;
- all exit, timeout, truncation, and termination facts are recorded;
- local execution remains restricted to trusted repository-controlled fixtures.

## Captured filesystem contracts

AXIOM-Bench uses `pathlib`, `tempfile`, and `shutil` only for deterministic
workspace assembly and artifact retention.

Implementation laws:

- all contract paths use POSIX-style relative paths;
- absolute paths, backslashes, `.` and `..` path components are rejected;
- resolved paths must remain under the declared task root or workspace;
- symbolic links in copied task material are rejected rather than followed;
- workspace files are created from exact bytes and hashed after creation;
- candidate mutation is restricted to the task allowlist;
- temporary workspaces are removed after bundle material is copied out;
- no task may mutate repository source or benchmark control files.

`TemporaryDirectory` cleanup is a lifecycle convenience, not isolation from the
host filesystem.

## Captured hashing and archive contracts

`hashlib.sha256` is used for source, trace, command, attempt, manifest, and
bundle content identifiers.

`zipfile.ZipInfo` permits AXIOM-Bench to set deterministic entry timestamps,
permission metadata, paths, compression type, and sorted insertion order.

The runner distinguishes:

- raw Evidence containing timestamps and durations;
- canonical semantic hashes that exclude explicitly declared volatile fields;
- deterministic conformance ZIPs whose retained semantic files contain no
  wall-clock values.

A GitHub artifact wrapper may differ between runs. Reproducibility is judged on
the normalized inner AXIOM-Bench bundle.

## Stream-limit implementation

The standard library does not provide a single hardened `max_output_bytes`
option for `Popen` pipes. AXIOM-Bench therefore uses two reader threads that:

1. read fixed-size byte chunks from stdout and stderr;
2. append only while the shared retained-output budget remains available;
3. set an overflow signal when the combined cap is exceeded;
4. cause the parent to terminate/kill and reap the process;
5. retain the exact bounded prefixes and mark the command as output-limited.

This controls retained output and prevents unbounded Python memory buffering. It
is not a disk, CPU, memory, syscall, namespace, or process-tree sandbox.

## Trust decision

Classification:

```text
CAPABILITY_PROVIDER
```

The standard library is sufficient for deterministic trusted conformance
execution and replay. No third-party process runner is introduced.

The local executor accepts only:

```text
trusted_reference
trusted_seeded_wrong
```

`replay_only` executes no subprocess. `untrusted_model_output` is rejected before
workspace candidate application with stable reason:

```text
AX-BENCH-SANDBOX-REQUIRED
```

## Explicit limitations

The runner does not claim:

- OS-level sandboxing;
- containment of malicious subprocess trees;
- filesystem namespaces;
- syscall filtering;
- CPU or memory quotas enforced by the operating system;
- network isolation;
- safety for arbitrary model-generated code;
- equivalence to Docker, a VM, or an Inspect sandbox extension.

An approved isolated backend remains required before live candidate execution.
