# Proof Status — v0.4.0

## Passed in the sandbox

- Agent A implementation suite: **22/22**
- Agent B adversarial review: **23/23**
- Evidence layers: **38/38**
- clean interpreter/native loop result: `55 == 55`
- signed division/remainder fixture: `17 == 17`
- all seven arithmetic panic classes match interpreter/native identity and code

### Checked `i32` fault matrix

```text
addition overflow      101  i32_add_overflow
subtraction overflow   102  i32_sub_overflow
multiplication overflow 103 i32_mul_overflow
division by zero       104  i32_divide_by_zero
division overflow      105  i32_divide_overflow
remainder by zero      106  i32_remainder_by_zero
remainder overflow     107  i32_remainder_overflow
```

### Compiler and platform layers retained

- strict UTF-8 source loading and SHA-256
- exact token spans
- parser and deterministic AST
- canonical formatter and structural round trip
- name/type checking and stable diagnostics
- lexical mutation and loops
- HIR, CFG, effects, ownership summary
- native x86_64 Clang build
- C ABI link/call
- script profile
- WebAssembly binary artifact
- RISC-V ELF relocatable object
- JSON Schema Draft 2020-12 validation
- deterministic stage output

## Not proven

- Rust bootstrap compilation in this sandbox
- wrapping, saturating, or unchecked arithmetic modes
- full ownership/lifetime semantics
- full effect/capability system
- WebAssembly runtime execution
- bare-metal execution in emulator/hardware
- GPU execution
- LSP
- package ecosystem
- self-hosting
- Axiom 1.0
