# M1 Trusted Conformance Runner Source Evidence

Status: authoritative implementation evidence for the provider-free M1 runner  
Applies to: issue #12  
Python baseline: 3.11

## Resolved source

The implementation is based on the official CPython 3.11 standard-library
contracts for `subprocess`, `pathlib`, `tempfile`, `shutil`, `hashlib`, and
`zipfile`.

Resolved Context7 source:

```text
/python/cpython/v3.11.14
```

## Process contracts

AXIOM-Bench uses `subprocess.Popen` with an argument sequence and
`shell=False`.

Relevant source contracts:

- an argument sequence preserves argument boundaries;
- `cwd` changes the child working directory before execution;
- an explicit `env` mapping replaces inherited environment variables;
- `stdout=PIPE` and `stderr=PIPE` expose byte streams;
- `poll()`, `wait()`, `terminate()`, and `kill()` provide lifecycle controls;
- timeout handling must terminate or kill and then reap the child;
- `communicate()` avoids pipe deadlocks but uses in-memory buffering unsuitable
  for an explicit retained-output cap;
- `start_new_session=True` creates a POSIX session but is not a sandbox or a
  complete cross-platform process-tree boundary;
- Windows process creation and termination differ from POSIX;
- `shell=False` prevents shell interpretation but does not make an executable
  safe.

Implementation decisions:

- argument arrays only;
- no shell expansion, pipes, redirection, or command substitution;
- explicit temporary workspace as `cwd`;
- minimal deterministic environment allowlist;
- concurrent bounded byte readers;
- per-command and total-task timeout handling;
- output, feedback, invocation, candidate-byte, single-file, and changed-line
  limits;
- structured `not_started` Evidence when process creation fails;
- local execution restricted to repository-controlled trusted fixtures.

## Filesystem contracts

AXIOM-Bench uses `pathlib`, `tempfile`, and `shutil` for workspace assembly and
artifact retention.

Implemented laws:

- contract paths use exact normalized POSIX relative spelling;
- absolute paths, backslashes, dot components, Windows drive/stream separators,
  and root escapes are rejected;
- resolved task paths remain below the task root;
- resolved candidate paths remain below the temporary workspace;
- symbolic links in selected task source paths are rejected;
- the selected candidate is written as exact bytes to one declared workspace
  path;
- caller-selected output directories must not already exist;
- output directories inside the repository or task root are rejected;
- temporary workspaces are removed after retained Evidence is copied out.

The runner controls where it applies the candidate and where it writes its own
Evidence. It does **not** claim to observe or prevent every filesystem access
made by a trusted child process. Trusted fixture commands execute with the host
account's available authority. That is why model-generated code remains
forbidden locally.

`TemporaryDirectory` cleanup is lifecycle management, not host isolation.

## Path and archive contracts

`hashlib.sha256` identifies source, candidate, trace, command, attempt, report,
manifest, and bundle content.

`zipfile.ZipInfo` permits deterministic timestamps, permissions, path spelling,
compression type, and sorted insertion order.

Canonical bundle construction uses:

- sorted normalized POSIX paths;
- fixed entry timestamps;
- fixed regular-file permissions;
- canonical JSON;
- deterministic compression parameters;
- no raw timing records.

Replay additionally rejects:

- duplicate paths;
- case-folded or Unicode-normalized portable collisions;
- directory entries;
- encrypted entries;
- symbolic links;
- excessive entry count, individual size, or total size;
- unsafe paths read from either ZIP metadata or internal JSON documents.

A GitHub artifact wrapper may differ between runs. Reproducibility is judged on
the normalized inner AXIOM Evidence and conformance ZIPs.

## Bounded stream implementation

The standard library has no hardened `max_output_bytes` option for `Popen`
pipes. AXIOM-Bench therefore uses two reader threads that:

1. read fixed-size byte chunks from stdout and stderr;
2. append only while the shared retained-output budget remains;
3. signal overflow when the combined cap is exceeded;
4. cause the parent to terminate, kill if needed, and reap the child;
5. retain bounded prefixes and record `output_limited`.

This bounds retained Python memory for command output. It is not a disk, CPU,
memory, syscall, namespace, network, or process-tree sandbox.

## Replay contracts

Replay extracts only validated entries into a fresh temporary directory and
safely resolves every path referenced by the manifest, report, attempt, command
records, and stream records.

Replay verifies:

- exact archive file set;
- file hashes and sizes;
- manifest semantic identity;
- attempt/report/task/language/adapter consistency;
- canonical attempt and trace links;
- command and stream links;
- trace schema and sequence;
- full-success and conformance decisions.

Replay starts no subprocess and applies no candidate workspace.

## Trust classification

Python's standard library is classified as:

```text
CAPABILITY_PROVIDER
```

It is sufficient for deterministic trusted conformance and replay. No
third-party process runner is introduced.

Accepted local trust classes:

```text
trusted_reference
trusted_seeded_wrong
```

`replay_only` executes no process. `untrusted_model_output` is rejected before
candidate application with:

```text
AX-BENCH-SANDBOX-REQUIRED
```

## Explicit limitations

The runner does not claim:

- safety for arbitrary model-generated code;
- OS-level sandboxing;
- complete child process-tree containment;
- complete host filesystem mutation confinement;
- filesystem namespaces or syscall filtering;
- CPU, memory, disk, or network quotas enforced by the operating system;
- equivalence to Docker, a VM, a cloud sandbox, or an Inspect sandbox extension.

An approved isolated backend remains required before live candidate execution.
