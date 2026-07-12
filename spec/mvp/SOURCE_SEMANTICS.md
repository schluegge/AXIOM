# AXIOM Next MVP source semantics

Status: proposed normative contract; no implementation claim

The MVP source language is UTF-8 text and will contain only modules with
functions, `fn`, `pub`, `let`, `if`, `else`, `return`, calls, `bool`, `i64`,
`text`, unit, `Result<T,E>`, `ok`, `err`, `try`, equality, checked integer
arithmetic, and the host functions `fs.read_text` and `fs.write_text`.

Evaluation order is left to right. Integer arithmetic is checked. Public
functions have explicit parameter and result types. There is no null, exception,
implicit numeric conversion, ambient I/O, implicit package acquisition, or
silent source repair.

The sole MVP entry point is:

```axiom
pub fn run(input: text, output: text) -> Result<(), AppError>
```
