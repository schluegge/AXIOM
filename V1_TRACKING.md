# AXIOM v1 Tracking

Canonical program issue: [#9](https://github.com/schluegge/AXIOM/issues/9)  
Release gate: [#25](https://github.com/schluegge/AXIOM/issues/25)  
Machine-readable graph: [`roadmap/v1.json`](roadmap/v1.json)  
Canonical technical roadmap: [`MVP_ROADMAP.md`](MVP_ROADMAP.md)  
Active milestone: **M1 / issue #12**

## Release definition

AXIOM v1.0 is the first stable release for safe, deterministic local CLI and
structured-data software. It is not a claim that every systems-programming
domain is complete.

The AI-first superiority statement is permitted only if M13 records `MVP_PASS`
under [`AI_FIRST_MVP_CONTRACT.md`](AI_FIRST_MVP_CONTRACT.md). A technically
usable v1 may still be released without that statement when all correctness and
product gates pass and the benchmark result is reported honestly.

## Ordered milestone graph

| ID | GitHub issue | State in contract | Depends on | Outcome |
|---|---:|---|---|---|
| M0 | [#11](https://github.com/schluegge/AXIOM/issues/11) | complete | roadmap PR #10 | Project authority and consistency |
| M1 | [#12](https://github.com/schluegge/AXIOM/issues/12) | active | M0 | AXIOM-Bench 0.1 |
| M2 | [#13](https://github.com/schluegge/AXIOM/issues/13) | blocked | M1 | Rust bootstrap v0.7 parity |
| M3 | [#14](https://github.com/schluegge/AXIOM/issues/14) | blocked | M2 | Compiler/AI interaction protocol |
| M4 | [#15](https://github.com/schluegge/AXIOM/issues/15) | blocked | M3 | Scalar completeness |
| M5 | [#16](https://github.com/schluegge/AXIOM/issues/16) | blocked | M4 | Variants and typed failure |
| M6 | [#17](https://github.com/schluegge/AXIOM/issues/17) | blocked | M5 | Minimal monomorphized generics |
| M7 | [#18](https://github.com/schluegge/AXIOM/issues/18) | blocked | M6 | Ownership and deterministic destruction |
| M8 | [#19](https://github.com/schluegge/AXIOM/issues/19) | blocked | M7 | Bytes, slices, strings, and lists |
| M9 | [#20](https://github.com/schluegge/AXIOM/issues/20) | blocked | M8 | Modules and reproducible projects |
| M10 | [#21](https://github.com/schluegge/AXIOM/issues/21) | blocked | M9 | Effects and capabilities |
| M11 | [#22](https://github.com/schluegge/AXIOM/issues/22) | blocked | M10 | Minimal standard library and JSON |
| M12 | [#23](https://github.com/schluegge/AXIOM/issues/23) | blocked | M11 | Golden applications and hardening |
| M13 | [#24](https://github.com/schluegge/AXIOM/issues/24) | blocked | M12 | Frozen holdout and release decision |
| V1 | [#25](https://github.com/schluegge/AXIOM/issues/25) | blocked | M13 | Stable `v1.0.0` release gate |

Only one milestone may have status `active`. Completion must move from top to
bottom without skipping a dependency.

## Completed transition

M0 was completed by PR #27. Its exact head passed the roadmap contract and two
complete repository-proof executions with byte-identical inner Evidence ZIPs:

```text
6f615e62c6a3347792ea4d9611904498512f53a3359dd84707c9c0928880bbeb
```

## GitHub controls

- `.github/ISSUE_TEMPLATE/axiom-capability.yml` requires blocker, milestone,
  AI-failure hypothesis, source evidence, semantic impact, proof, benchmark, and
  non-goals for new capabilities.
- `.github/pull_request_template.md` requires source evidence, vertical
  implementation, proof matrix, benchmark delta, and exact-PR Evidence.
- `.github/workflows/v1-roadmap-contract.yml` checks the local roadmap contract
  and live GitHub issues on roadmap PRs, pushes, issue changes, and manual runs.
- `tools/check_v1_roadmap.py` emits deterministic JSON with stable
  `AX-ROADMAP-*` findings.

## Post-v1 holding area

Issue [#8](https://github.com/schluegge/AXIOM/issues/8) for raw pointers and
user-visible `unsafe` remains explicitly post-v1. Networking, concurrency,
async, GUI, GPU, kernel/bare-metal, public package registry, macros, reflection,
custom allocators, additional targets, and self-hosting require separate
post-v1 decisions and evidence.
