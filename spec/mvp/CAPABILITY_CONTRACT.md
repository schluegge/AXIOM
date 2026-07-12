# AXIOM Next MVP capability contract

Status: proposed; implementation begins after Task 10

The MVP admits exactly two guest capabilities:

- `capability.fs.read-text`
- `capability.fs.write-text`

No clock, randomness, networking, process spawning, environment access, ambient
filesystem authority, or unrestricted WASI world is permitted. Paths must remain
inside an explicitly granted root. Absolute paths, traversal with `..`, and
symlink escape are rejected fail-closed.
