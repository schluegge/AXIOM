# Context7 Source Evidence

Context7 was used before implementing and executing the sandbox proof.

## Cargo

Resolved library:

```text
/websites/doc_rust-lang_cargo
```

Queried facts:

- `--frozen` is equivalent to `--locked` plus `--offline`.
- `cargo test --no-fail-fast` continues across test executables instead of
  stopping after the first failed executable.
- arguments after `--` are passed to the executed binary/test target.

Application:

- retained in the Rust Phase 1 runner and documentation
- not claimed as sandbox-executed because no Rust toolchain was available

## Rust standard library

Resolved library:

```text
/rust-lang/rust
```

Queried facts:

- `std::process::Command::status()` executes a child and exposes an
  `ExitStatus` whose `success()` method reports success.
- `Command::output()` captures stdout, stderr, and exit status.
- `std::fs::write()` creates/truncates and writes a complete file.
- `std::fs::read_to_string()` rejects invalid UTF-8.

Application:

- confirms the intended Rust bootstrap implementation contracts
- current sandbox executable prototype uses Python subprocess/filesystem APIs
  because Rust binaries could not be acquired in this environment

## rustup

Resolved library:

```text
/rust-lang/rustup
```

Queried facts:

- non-interactive install uses `-y`
- `--default-toolchain none` installs rustup without a default toolchain
- `--profile minimal` selects the minimal component profile
- `CARGO_HOME` and `RUSTUP_HOME` select isolated storage
- `RUSTUP_TOOLCHAIN` overrides the selected toolchain

Application:

- retained in the Windows runner
- sandbox download was blocked before rustup could be installed

## LLVM

Resolved library:

```text
/websites/llvm
```

Queried facts:

- module/function syntax uses `define ... @name(...) { ... }`
- integer addition uses `add`
- integer comparison uses `icmp`
- conditional control flow uses `br i1 ..., label ..., label ...`
- functions return through `ret`
- textual LLVM IR can be compiled by Clang with `-x ir`

Application:

- `axiom_proof/llvm_backend.py`
- native x86_64 differential proof
- C ABI object and harness proof
- WebAssembly module artifact
- RISC-V freestanding ELF object

## Evidence boundary

Context7 supplied current documentation evidence. Deterministic local tools,
not Context7 or an AI model, produced the executable proof results.

## LLVM checked arithmetic — v0.4.0

Resolved library:

```text
/llvm/llvm-project
```

Queried official facts:

- `llvm.sadd.with.overflow.i32`, `llvm.ssub.with.overflow.i32`, and
  `llvm.smul.with.overflow.i32` return `{i32, i1}` containing the modulo result
  and a signed-overflow flag.
- `extractvalue` reads the result and overflow fields.
- LLVM `sdiv` rounds signed division toward zero.
- LLVM `sdiv` has undefined behavior for division by zero and signed overflow.
- LLVM `srem` has undefined behavior for division by zero and signed overflow.
- conditional branches and terminated failure blocks are required around
  guarded operations.

Application:

- `axiom_proof/llvm_backend.py`
- `runtime/axiom_runtime.c`
- `ARITHMETIC_SEMANTICS.md`
- checked-arithmetic differential corpus

Evidence boundary:

Context7 established the source-level LLVM contracts. Clang execution and the
interpreter/native differential corpus establish the local proof.
