"""Publish files to the archive repository through the GitHub REST API.

Reads use the Contents API; writes go through the Git Data API so that all
files of one approval land in a single commit.
"""
from __future__ import annotations

import base64

import httpx


class GitHubError(RuntimeError):
    pass


class GitHubPublisher:
    def __init__(self, token: str, repo: str, branch: str = "main",
                 api_base: str = "https://api.github.com", client: httpx.Client | None = None):
        if not token or not repo:
            raise GitHubError("GITHUB_TOKEN and GITHUB_REPO must be configured")
        self.repo = repo
        self.branch = branch
        self.api = api_base.rstrip("/")
        self.client = client or httpx.Client(timeout=60)
        self.client.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "wp-portal",
        })

    def _url(self, path: str) -> str:
        return f"{self.api}/repos/{self.repo}/{path.lstrip('/')}"

    def _check(self, r: httpx.Response) -> dict:
        if r.status_code >= 400:
            raise GitHubError(f"GitHub API {r.request.method} {r.request.url} -> "
                              f"{r.status_code}: {r.text[:300]}")
        return r.json()

    def get_text(self, path: str) -> str | None:
        """Current content of a text file on the branch, or None if absent."""
        r = self.client.get(self._url(f"contents/{path}"), params={"ref": self.branch})
        if r.status_code == 404:
            return None
        data = self._check(r)
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        # Large files come without inline content; fetch via download_url.
        if data.get("download_url"):
            r2 = self.client.get(data["download_url"])
            self._check(r2)
            return r2.text
        return None

    def commit_files(self, files: dict[str, bytes], message: str) -> str:
        """Create one commit adding/updating ``files`` ({path: content}); returns its URL."""
        ref = self._check(self.client.get(self._url(f"git/ref/heads/{self.branch}")))
        head_sha = ref["object"]["sha"]
        head_commit = self._check(self.client.get(self._url(f"git/commits/{head_sha}")))
        base_tree = head_commit["tree"]["sha"]

        tree = []
        for path, content in files.items():
            blob = self._check(self.client.post(self._url("git/blobs"), json={
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
            }))
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})

        new_tree = self._check(self.client.post(self._url("git/trees"),
                                                json={"base_tree": base_tree, "tree": tree}))
        commit = self._check(self.client.post(self._url("git/commits"), json={
            "message": message, "tree": new_tree["sha"], "parents": [head_sha],
        }))
        self._check(self.client.patch(self._url(f"git/refs/heads/{self.branch}"),
                                      json={"sha": commit["sha"], "force": False}))
        return commit.get("html_url") or f"https://github.com/{self.repo}/commit/{commit['sha']}"
