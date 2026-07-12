# REV-2 Deterministic Review Gate Source Evidence

Status: authoritative implementation evidence for the deterministic
pull-request review gate  
Applies to: issue #34  
Python baseline: 3.11

## Resolved sources

Resolved Context7 sources:

```text
/websites/github_en_actions   (docs.github.com/en/actions)
```

External component classification:

- GitHub Actions workflow and event contracts — `ADAPTER_TARGET`;
- `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` —
  `ADAPTER_TARGET`, immutable-SHA pinned only;
- PyYAML `yaml.safe_load` — `CAPABILITY_PROVIDER` for reading repository
  workflow files;
- GitHub-hosted runner filesystem layout — `REFERENCE_ONLY`.

## GitHub token permission contracts

Source: `docs.github.com/en/actions/…/workflow-syntax-for-github-actions` and
`…/security-guides/automatic-token-authentication`.

- The `permissions` key modifies `GITHUB_TOKEN` access for a whole workflow or
  for one job; job-level configuration overrides workflow-level configuration.
- When any scope is listed, every unlisted scope becomes `none`.
- Scope values are `read`, `write`, or `none` (`id-token` has no `read`).
- `read-all` and `write-all` are whole-token shorthand forms.
- Workflows triggered by `pull_request` from a forked repository run with
  read-only token permissions and without repository secrets.

Implementation decisions:

- the gate parses the exact `permissions` mappings of every repository
  workflow and compares them against a versioned machine-readable allowlist;
- shorthand `write-all`, unknown scopes, and any scope wider than the
  allowlist are blocking findings;
- an unlisted workflow file receives the strictest default allowlist
  (`contents: read` only) so a new workflow cannot widen authority silently.

## Untrusted pull-request execution contracts

Source: `docs.github.com/en/actions/reference/security/securely-using-pull_request_target`
and `…/reference/secure-use-reference`.

- `pull_request_target` (and `workflow_run`) workflows are privileged: they
  can hold write tokens and secrets while event content is attacker
  controlled.
- Checking out the pull-request head inside a `pull_request_target` workflow
  executes untrusted fork code with elevated authority ("pwn request").
- Plain `pull_request` fork runs are the documented untrusted-code boundary:
  read-only token, no secrets.

Implementation decisions:

- any occurrence of a `pull_request_target` trigger in any repository
  workflow is a blocking finding;
- the deterministic review workflow itself uses `pull_request` with
  `contents: read` and publishes no comments.

## Action pinning contracts

Source: `docs.github.com/en/actions/reference/security/secure-use` and
`…/how-tos/administering-github-actions/managing-custom-actions`.

- Pinning an action to a full-length 40-character commit SHA is the only
  immutable reference form; tags and branches are mutable.

Implementation decisions:

- every `uses:` reference to an external action must end in
  `@<40-hex-SHA>`; tag, branch, and shortened-SHA references are blocking
  findings;
- local composite references (`./path`) and `docker://` references are absent
  from this repository and are rejected until a policy entry approves them.

## Event payload contracts

Source: `docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows`,
`…/contexts`, and `…/github-hosted-runners-reference`.

- `GITHUB_EVENT_PATH` names a JSON file containing the exact webhook payload.
- For `pull_request` events, `GITHUB_SHA` is the merge-branch commit; the
  exact reviewed head is `github.event.pull_request.head.sha` and the base is
  `github.event.pull_request.base.sha`.
- `actions/checkout` checks out the merge branch by default; reviewing the
  exact head requires an explicit `ref`.

Implementation decisions:

- the review workflow checks out `github.event.pull_request.head.sha`
  explicitly;
- the gate reads repository, pull-request number, base SHA, and head SHA from
  the event file and verifies that the checked-out `HEAD` equals the declared
  head SHA;
- a missing, malformed, or field-incomplete event file fails closed before
  any check executes.

## YAML parsing contract

PyYAML `yaml.safe_load` constructs only standard Python data types and does
not execute arbitrary object constructors; it resolves anchors, aliases, flow
mappings, and quoting, which regex-based scanning would miss. The proof
dependency set pins `PyYAML==6.0.1` (already the Python 3.11 baseline in this
repository's CI image family).

Implementation decisions:

- workflow files are read with `yaml.safe_load` only;
- a workflow file that fails to parse, or whose parsed shape is not the
  expected mapping structure, is a blocking finding (fail closed), never a
  skip.

## Explicit non-evidence boundary

This document does not authorize comment publication, AI review, merge
automation, artifact consumption across workflows, or `workflow_run`
processing. Those remain governed by issues #35 through #41.
