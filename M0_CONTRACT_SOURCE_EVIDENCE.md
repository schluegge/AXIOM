# M0 Project Contract Source Evidence

Status: authoritative dependency evidence for M0  
Applies to: issue #11  
Recorded validator version: `jsonschema==4.25.1`

## Resolved Context7 source

```text
/python-jsonschema/jsonschema/v4.25.1
```

The source is the official `python-jsonschema/jsonschema` project documentation
for release 4.25.1.

## Selected standard

The AXIOM project contract uses JSON Schema Draft 2020-12 explicitly.

The schema declares:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema"
}
```

The checker does not infer or automatically upgrade the schema draft.

## Captured APIs

```python
from jsonschema import Draft202012Validator

Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
errors = sorted(validator.iter_errors(instance), key=...)
```

Captured contracts:

- `Draft202012Validator.check_schema(schema)` validates the schema itself against
  the bundled Draft 2020-12 meta-schema and raises a schema error for an invalid
  contract schema;
- constructing `Draft202012Validator(schema)` pins validation behavior to Draft
  2020-12 rather than selecting a draft implicitly;
- `iter_errors(instance)` performs lazy validation and allows AXIOM to report all
  independent schema failures in deterministic order;
- every validation error exposes `message`, `path`, `schema_path`, and
  `validator`, which are preserved in the machine-readable checker report;
- the library supports Draft 2020-12 directly in the selected release.

## Offline boundary

AXIOM's schema contains only local `#/$defs/...` references. The checker rejects
non-local `$ref` values before validator construction. It does not configure a
remote registry, URL retrieval handler, or network client.

Package installation may occur in CI before the checker starts. Contract
validation itself performs no network access.

## Dependency decision

Classification: `CAPABILITY_PROVIDER`

AXIOM reuses `jsonschema` rather than implementing JSON Schema. The complete
resolved proof dependency closure is exactly pinned in `requirements-proof.txt`:

```text
attrs==26.1.0
jsonschema==4.25.1
jsonschema-specifications==2025.9.1
referencing==0.37.0
rpds-py==2026.6.3
typing-extensions==4.16.0
```

The checker derives its dependency evidence from that file and fails when a pin
is missing, duplicated, not installed, or does not match the installed version.
The exact versions are also persisted in the GitHub Evidence artifact.

## Non-decisions

This evidence does not authorize:

- a generalized policy engine;
- remote schema resolution;
- runtime dependency installation;
- a package manager;
- replacing AXIOM semantic analysis with JSON Schema;
- treating a schema-valid contract as proof that the compiler semantics are
  correct.
