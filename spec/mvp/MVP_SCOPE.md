# AXIOM Next MVP scope

Status: normative for Tasks 0–18
Contract: `contracts/mvp.json`

The MVP proves one architecture path, not a generally useful language release.
It preserves UTF-8 source text as the persisted product format and will later
connect a lossless Rust frontend, verified typed HIR, deterministic interpreter,
WebAssembly Component backend, and capability-limited runner.

Tasks 0–2 establish only the legacy boundary, build workspace, and normative
contracts. They introduce no parser, runtime behavior, Wasm backend, language
syntax, or superiority claim.

The only accepted architecture claim after Tasks 0–2 is:

> AXIOM Next has a deterministic, machine-checked project boundary from which
> implementation may begin.
