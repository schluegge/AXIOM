from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .publisher_core import PublicationRejected, _SHA40, _reject


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


def _default_http_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    max_bytes: int,
    follow_redirects: bool,
) -> HttpResponse:
    import urllib.error
    import urllib.request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, response_headers, newurl):  # noqa: ANN001
            return None

    opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        response = opener.open(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    try:
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise PublicationRejected("HTTP response exceeds byte limit")
        return HttpResponse(
            int(response.status),
            {str(key): str(value) for key, value in response.headers.items()},
            payload,
        )
    finally:
        response.close()


class GitHubRestApi:
    """Minimal GitHub REST client for the trusted review-publisher workflow."""

    API_VERSION = "2026-03-10"

    def __init__(self, token: str, *, api_url: str = "https://api.github.com", transport=None) -> None:
        _reject(not isinstance(token, str) or not token, "GitHub token is missing")
        _reject(not api_url.startswith("https://"), "GitHub API URL must use HTTPS")
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._transport = transport or _default_http_transport

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "axiom-review-publisher/0.1.0",
            "X-GitHub-Api-Version": self.API_VERSION,
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        max_bytes: int = 2_000_000,
    ) -> Any:
        encoded = None
        headers = self._headers()
        if payload is not None:
            encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        response = self._transport(
            method,
            f"{self._api_url}{path}",
            headers,
            encoded,
            max_bytes,
            True,
        )
        if response.status < 200 or response.status >= 300:
            detail = response.body.decode("utf-8", errors="replace")[:1000]
            raise PublicationRejected(f"GitHub API {method} {path} failed with {response.status}: {detail}")
        if not response.body:
            return None
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PublicationRejected(f"GitHub API {method} {path} returned invalid JSON") from error

    def list_run_artifacts(self, repository: str, run_id: int) -> list[dict[str, Any]]:
        value = self._request_json(
            "GET", f"/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"
        )
        if not isinstance(value, dict) or not isinstance(value.get("artifacts"), list):
            raise PublicationRejected("GitHub artifact listing has invalid shape")
        return [item for item in value["artifacts"] if isinstance(item, dict)]

    def download_artifact(self, repository: str, artifact_id: int, *, max_bytes: int) -> bytes:
        response = self._transport(
            "GET",
            f"{self._api_url}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
            self._headers(),
            None,
            64_000,
            False,
        )
        location = next(
            (value for key, value in response.headers.items() if key.lower() == "location"),
            None,
        )
        if response.status != 302 or not isinstance(location, str):
            raise PublicationRejected(f"GitHub artifact download did not return a redirect: {response.status}")
        if not location.startswith("https://"):
            raise PublicationRejected("GitHub artifact redirect must use HTTPS")
        signed_response = self._transport(
            "GET",
            location,
            {"User-Agent": "axiom-review-publisher/0.1.0"},
            None,
            max_bytes,
            True,
        )
        if signed_response.status != 200:
            raise PublicationRejected(
                f"signed artifact download failed with {signed_response.status}"
            )
        return signed_response.body

    def list_pull_requests_for_commit(
        self, repository: str, commit_sha: str
    ) -> list[dict[str, Any]]:
        _reject(_SHA40.fullmatch(commit_sha) is None, "commit SHA has invalid format")
        value = self._request_json(
            "GET", f"/repos/{repository}/commits/{commit_sha}/pulls?per_page=100"
        )
        if not isinstance(value, list):
            raise PublicationRejected("GitHub commit pull-request response has invalid shape")
        return [item for item in value if isinstance(item, dict)]

    def get_pull_request(self, repository: str, number: int) -> dict[str, Any]:
        value = self._request_json("GET", f"/repos/{repository}/pulls/{number}")
        if not isinstance(value, dict):
            raise PublicationRejected("GitHub pull request response has invalid shape")
        return value

    def list_pull_request_files(self, repository: str, number: int) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for page in range(1, 31):
            value = self._request_json(
                "GET",
                f"/repos/{repository}/pulls/{number}/files?per_page=100&page={page}",
            )
            if not isinstance(value, list):
                raise PublicationRejected("GitHub pull request files response has invalid shape")
            page_items = [item for item in value if isinstance(item, dict)]
            files.extend(page_items)
            if len(value) < 100:
                return files
        raise PublicationRejected("GitHub pull request file pagination exceeded limit")

    def list_issue_comments(self, repository: str, number: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        for page in range(1, 101):
            value = self._request_json(
                "GET",
                f"/repos/{repository}/issues/{number}/comments?per_page=100&page={page}",
            )
            if not isinstance(value, list):
                raise PublicationRejected("GitHub issue comments response has invalid shape")
            page_items = [item for item in value if isinstance(item, dict)]
            comments.extend(page_items)
            if len(value) < 100:
                return comments
        raise PublicationRejected("GitHub issue comment pagination exceeded limit")

    def create_issue_comment(self, repository: str, number: int, body: str) -> dict[str, Any]:
        value = self._request_json(
            "POST", f"/repos/{repository}/issues/{number}/comments", payload={"body": body}
        )
        if not isinstance(value, dict):
            raise PublicationRejected("GitHub create-comment response has invalid shape")
        return value

    def update_issue_comment(self, repository: str, comment_id: int, body: str) -> dict[str, Any]:
        value = self._request_json(
            "PATCH", f"/repos/{repository}/issues/comments/{comment_id}", payload={"body": body}
        )
        if not isinstance(value, dict):
            raise PublicationRejected("GitHub update-comment response has invalid shape")
        return value
