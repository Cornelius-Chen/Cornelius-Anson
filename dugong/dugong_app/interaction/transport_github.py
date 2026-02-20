from __future__ import annotations

import base64
import json
from pathlib import PurePosixPath
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .transport_base import TransportBase


class GithubTransport(TransportBase):
    def __init__(
        self,
        repo: str,
        token: str,
        source_id: str,
        branch: str = "main",
        folder: str = "dugong_sync",
    ) -> None:
        self.repo = repo
        self.token = token
        self.source_id = source_id
        self.branch = branch
        self.folder = folder.strip("/").replace("\\", "/")
        self.source_file = f"{self.source_id}.jsonl"
        self.presence_folder = "presence"
        self.presence_file = f"{self.source_id}.json"

    def send(self, payload: dict) -> None:
        line = json.dumps(payload, ensure_ascii=True)
        path = self._path(self.source_file)
        existing_text, sha = self._read_remote_file(path)
        next_text = f"{existing_text}\n{line}" if existing_text else line
        self._write_remote_file(path=path, text=next_text, sha=sha, message=f"sync({self.source_id}): append event")

    def receive(self) -> list[dict]:
        payloads, _next = self.receive_incremental({})
        return payloads

    def receive_incremental(self, cursors: dict[str, int] | None = None) -> tuple[list[dict], dict[str, int]]:
        current_cursors = dict(cursors or {})
        next_cursors: dict[str, int] = dict(current_cursors)
        payloads: list[dict] = []
        for name in self._list_remote_files():
            if not name.endswith(".jsonl"):
                continue
            if name == self.source_file:
                continue
            path = self._path(name)
            text, _sha = self._read_remote_file(path)
            lines = text.splitlines()
            offset = int(current_cursors.get(name, 0))
            if offset < 0 or offset > len(lines):
                offset = 0
            for line in lines[offset:]:
                if not line.strip():
                    continue
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            next_cursors[name] = len(lines)
        return payloads, next_cursors

    def _path(self, filename: str) -> str:
        return str(PurePosixPath(self.folder) / filename)

    def _presence_path(self, filename: str) -> str:
        return str(PurePosixPath(self.folder) / self.presence_folder / filename)

    def _base_url(self, path: str) -> str:
        encoded_path = quote(path, safe="/")
        return f"https://api.github.com/repos/{self.repo}/contents/{encoded_path}"

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dugong-sync/0.1",
        }

    def _api_request(self, method: str, url: str, body: dict | None = None) -> tuple[int, dict | list, dict[str, str]]:
        data = None
        headers = self._headers()
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url=url, data=data, method=method, headers=headers)
        try:
            with urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                payload = json.loads(raw) if raw else {}
                return resp.status, payload, dict(resp.headers.items())
        except HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            payload = json.loads(raw) if raw else {}
            return exc.code, payload, dict(exc.headers.items()) if exc.headers else {}

    def _list_remote_files(self) -> list[str]:
        url = f"{self._base_url(self.folder)}?ref={quote(self.branch)}"
        status, payload, resp_headers = self._api_request("GET", url)
        if status == 404:
            return []
        if status >= 400:
            raise RuntimeError(self._format_http_error("github list failed", status, resp_headers))
        if not isinstance(payload, list):
            return []

        names: list[str] = []
        for entry in payload:
            if isinstance(entry, dict) and entry.get("type") == "file" and isinstance(entry.get("name"), str):
                names.append(entry["name"])
        return names

    def _list_remote_presence_files(self) -> list[str]:
        path = str(PurePosixPath(self.folder) / self.presence_folder)
        url = f"{self._base_url(path)}?ref={quote(self.branch)}"
        status, payload, resp_headers = self._api_request("GET", url)
        if status == 404:
            return []
        if status >= 400:
            raise RuntimeError(self._format_http_error("github list presence failed", status, resp_headers))
        if not isinstance(payload, list):
            return []

        names: list[str] = []
        for entry in payload:
            if isinstance(entry, dict) and entry.get("type") == "file" and isinstance(entry.get("name"), str):
                names.append(entry["name"])
        return names

    def _read_remote_file(self, path: str) -> tuple[str, str | None]:
        url = f"{self._base_url(path)}?ref={quote(self.branch)}"
        status, payload, resp_headers = self._api_request("GET", url)
        if status == 404:
            return "", None
        if status >= 400 or not isinstance(payload, dict):
            raise RuntimeError(self._format_http_error("github read failed", status, resp_headers))

        b64 = payload.get("content", "")
        if not isinstance(b64, str):
            b64 = ""
        decoded = base64.b64decode(b64.encode("utf-8")).decode("utf-8") if b64 else ""
        sha = payload.get("sha")
        return decoded.strip("\n"), sha if isinstance(sha, str) else None

    def _write_remote_file(self, path: str, text: str, sha: str | None, message: str) -> None:
        body: dict = {
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "branch": self.branch,
        }
        if sha:
            body["sha"] = sha
        status, _payload, resp_headers = self._api_request("PUT", self._base_url(path), body=body)
        if status >= 400:
            raise RuntimeError(self._format_http_error("github write failed", status, resp_headers))

    def _format_http_error(self, prefix: str, status: int, headers: dict[str, str]) -> str:
        if status != 429:
            return f"{prefix}: status={status}"
        reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
        if reset:
            return f"{prefix}: status=429 rate_limit_reset={reset}"
        return f"{prefix}: status=429"

    def update_presence(self, presence: dict) -> None:
        text = json.dumps(presence, ensure_ascii=True, separators=(",", ":"))
        path = self._presence_path(self.presence_file)
        _existing_text, sha = self._read_remote_file(path)
        self._write_remote_file(path=path, text=text, sha=sha, message=f"sync({self.source_id}): presence")

    def receive_presence(self) -> list[dict]:
        payloads: list[dict] = []
        for name in self._list_remote_presence_files():
            if not name.endswith(".json"):
                continue
            if name == self.presence_file:
                continue
            path = self._presence_path(name)
            text, _sha = self._read_remote_file(path)
            if not text.strip():
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                payloads.append(data)
        return payloads
