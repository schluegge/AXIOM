# AXIOM Next MVP diagnostic contract

Status: proposed; implementation begins after Task 6

Every diagnostic has a stable code, severity, message key, primary UTF-8 byte
span, line/column projection, related spans, compiler-known facts, and schema
version. Text and JSON renderings must represent the same semantic facts.

The initial code families are `AX-LEX`, `AX-PARSE`, `AX-NAME`, `AX-TYPE`,
`AX-RESULT`, `AX-CAP`, `AX-HIR`, `AX-CODEGEN`, and `AX-RUN`. Candidate actions
may refer only to symbols and transformations proven available by the compiler.
