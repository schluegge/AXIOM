# REV-3 Safe Review Publisher Source Evidence

Status: authoritative implementation evidence for issue #35  
Captured: 2026-07-12  
Python baseline: 3.11

## Component classification

- GitHub `workflow_run` event and REST API — `ADAPTER_TARGET`.
- `actions/checkout` and `actions/setup-python` — `ADAPTER_TARGET`, pinned by
  immutable full commit SHA.
- Python `zipfile`, `urllib.request`, `hashlib`, and `json` —
  `CAPABILITY_PROVIDER` from the standard library.
- Existing AXIOM report schema, semantic validator, canonicalizer, and renderer
  — `CAPABILITY_PROVIDER`; the publisher does not create a second review
  contract.

No new orchestration framework, bot application, external service, or model
provider is introduced.

## Privilege-separation contract

Source:
`https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run`

Exact source facts used:

- `workflow_run` executes when another workflow is requested, in progress, or
  completed.
- The workflow file must exist on the default branch.
- A `workflow_run` workflow can receive secrets and write tokens even when the
  triggering workflow was intentionally unprivileged.
- GitHub warns that executing untrusted code in this privileged context can
  expose write authority or secrets.
- The triggering workflow's event payload and artifacts are available to the
  `workflow_run` workflow.

Implementation decisions:

- `.github/workflows/deterministic-review.yml` remains a `pull_request` workflow
  with `contents: read` only and uploads a digest-bound publication envelope.
- `.github/workflows/publish-review.yml` is triggered only by completion of the
  named deterministic workflow.
- The publisher checks out only
  `${{ github.event.repository.default_branch }}` with persisted checkout
  credentials disabled. It never checks out `workflow_run.head_sha`, a PR ref,
  or artifact contents.
- Publisher permissions are exactly `actions: read`, `contents: read`, and
  `pull-requests: write`.

## Artifact API contract

Source:
`https://docs.github.com/en/rest/actions/artifacts?apiVersion=2026-03-10`

Exact endpoints used:

```text
GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts?per_page=100
GET /repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip
```

The artifact-list endpoint requires Actions read permission. The archive
endpoint returns an HTTP redirect to a temporary download URL.

Implementation decisions:

- The expected artifact name is derived from the trusted workflow-run ID and
  exactly one non-expired match is required.
- The authenticated API request does not automatically follow redirects.
- The temporary signed URL is required to use HTTPS and is fetched without the
  `Authorization` header, preventing credential forwarding to the artifact
  storage host.
- The response is byte-bounded before ZIP parsing.
- ZIP data is never extracted. Every member is read in memory only after checks
  for normalized relative paths, duplicates, directories, symbolic links,
  encryption, compression method, entry count, per-entry size, cumulative
  decompressed size, and compression ratio.

## Pull-request identity contract

Sources:

- `https://docs.github.com/en/rest/commits/commits?apiVersion=2026-03-10#list-pull-requests-associated-with-a-commit`
- `https://docs.github.com/en/rest/pulls/pulls?apiVersion=2026-03-10#get-a-pull-request`

Exact endpoints used:

```text
GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls?per_page=100
GET /repos/{owner}/{repo}/pulls/{pull_number}
```

The `workflow_run.pull_requests` list is treated only as an optional hint because
it may be empty for a fork-style delivery. The trusted publisher resolves the
exact `workflow_run.head_sha` through GitHub's commit-associated pull-request
endpoint and requires exactly one matching pull request. No match or an
ambiguous match fails closed before artifact acceptance. The pull-request
response then supplies the live `head.sha`; the publisher compares that value
with the exact reviewed head recorded by the workflow-run event, publication
envelope, and review report. The comment displays `CURRENT` or `STALE`;
staleness never changes the deterministic report itself.

## Pull-request comment contract

Source:
`https://docs.github.com/en/rest/issues/comments?apiVersion=2026-03-10`

Pull requests use issue-comment endpoints for top-level conversation comments.
The publisher uses:

```text
GET   /repos/{owner}/{repo}/issues/{issue_number}/comments
POST  /repos/{owner}/{repo}/issues/{issue_number}/comments
PATCH /repos/{owner}/{repo}/issues/comments/{comment_id}
```

Implementation decisions:

- Only a comment authored by `github-actions[bot]` with the stable hidden AXIOM
  marker is considered an existing publication. Human-authored marker forgeries
  are ignored.
- Zero trusted markers creates one comment; one updates that comment; multiple
  trusted markers fail closed.
- The marker records reviewed head, observed current head, workflow-run ID, and
  attempt. A current result outranks a stale result; otherwise run ID and attempt
  prevent rollback by older delivery.
- Deterministic and advisory sections are structurally separate. Advisory AI is
  explicitly reported as not run and has no blocking authority.
- The body is UTF-8 byte-bounded. Truncation retains identity, state, workflow
  link, and the full retained artifact link.

## Immutable Action pins

Source:
`https://docs.github.com/en/actions/reference/security/secure-use`

GitHub documents a full-length commit SHA as the only immutable way to pin an
Action release. All third-party `uses:` entries remain full 40-character SHA
pins and are also enforced by the existing deterministic workflow-security
check.

## Explicit non-goals

- no PR code execution in the privileged workflow;
- no model call or advisory AI review;
- no merge, approval, branch-policy, label, or issue-management authority;
- no change to the deterministic gate verdict;
- no artifact extraction to the workspace or temporary filesystem;
- no acceptance of foreign repository, wrong PR, wrong run, wrong head,
  malformed schema, digest mismatch, non-canonical report, or renderer drift.
