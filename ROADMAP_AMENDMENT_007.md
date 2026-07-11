# Roadmap Amendment 007 — Measurable AI-First MVP

Status: proposed  
Tracking issue: #9

## Trigger

AXIOM v0.7.0 established a vertically executed safe-reference path through the
Python/LLVM semantic oracle. The next previously proposed capability was raw
pointers and explicit `unsafe` blocks.

A critical roadmap review found that this sequence continued a conventional
systems-language deepening path without first proving AXIOM's defining product
claim: that the language is materially better for AI-driven development.

The repository also lacked:

- a canonical future roadmap separate from historical amendments;
- a falsifiable AI-first contract;
- a real first product domain;
- an external comparison benchmark;
- a production bootstrap compiler schedule;
- complete-program acceptance fixtures.

## Decision

Freeze semantic expansion at v0.7 while the MVP foundation is established.

AXIOM's first product domain is:

```text
safe deterministic local CLI and structured-data tools
```

The canonical implementation and release sequence is now defined by:

- `MVP_ROADMAP.md`;
- `AI_FIRST_MVP_CONTRACT.md`;
- tracking issue #9.

Historical amendments remain valid records of delivered decisions. They are no
longer an implicit future roadmap.

## Consequences

### Immediate

- issue #8 is deferred until after the MVP;
- no new user-visible raw-pointer or `unsafe` surface begins now;
- v0.7 receives a frozen benchmark seed;
- the Rust bootstrap compiler is moved before broad additional language growth;
- each later capability must state a real-program blocker and falsifiable
  AI-development hypothesis;
- language-only, compiler-assisted, agent, compiler-performance, and generated
  runtime results remain separate.

### MVP language order

The ordered foundation is:

1. project authority and document contracts;
2. benchmark seed;
3. Rust bootstrap parity for v0.7;
4. stable compiler interaction protocol;
5. complete scalar/conversion foundation;
6. algebraic variants, exhaustive matching, `Option`, and `Result`;
7. minimal generics;
8. moves, ownership, and deterministic destruction;
9. bytes, slices, UTF-8 strings, and lists;
10. modules, visibility, manifest, and lockfile;
11. declared external effects and capabilities;
12. minimal standard library and JSON;
13. golden applications and Windows/Linux release proof;
14. frozen holdout benchmark and release decision.

Exactly one language capability is active at a time.

## AI-first claim boundary

AXIOM may not claim measurable AI-first superiority merely because:

- its compiler tests pass;
- generated source is shorter;
- an agent can repair compiler errors;
- its own benchmark tasks favor its features;
- a single model or prompt performs well;
- compiler diagnostics provide more solution information than comparison tools.

The claim requires the hard gates in `AI_FIRST_MVP_CONTRACT.md`.

## Why raw pointers move after the MVP

Raw pointers are not rejected. They are deferred because they do not unlock the
first product domain and would widen the unsafe surface before AXIOM has:

- explicit expected failures;
- owned dynamic data;
- strings and slices;
- modules and projects;
- external-effect boundaries;
- real programs;
- a production compiler;
- an external AI-development benchmark.

The future raw-pointer design must be justified by a concrete FFI, hardware, or
runtime requirement and must preserve the safe MVP language.

## Exit condition

This amendment is accepted when:

- the canonical roadmap and AI-first contract are merged;
- issue #9 is the active MVP tracker;
- issue #8 records its post-MVP dependency;
- AGENTS and README point to the new authority;
- the next implementation PR is M0 document/feature-contract consistency work,
  not new language syntax.
