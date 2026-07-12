# AXIOM Next MVP HIR contract

Status: proposed; implementation begins after Task 8

Typed HIR is the operational compiler contract, not the persisted user format.
Every HIR module must be produced from successfully analysed source and pass a
standalone verifier before interpretation or code generation.

The verifier will reject unknown IDs, type mismatches, missing reachable returns,
invalid `try` error types, undeclared host capabilities, duplicate function IDs,
and references to nonexistent nodes. Invalid HIR is never repaired downstream.
Canonical HIR JSON will be deterministic and include source spans and digests.
