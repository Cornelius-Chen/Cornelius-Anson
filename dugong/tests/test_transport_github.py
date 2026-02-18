from dugong_app.interaction.transport_github import GithubTransport


def test_github_transport_send_appends_line(monkeypatch) -> None:
    gt = GithubTransport(repo="owner/repo", token="t", source_id="cornelius", branch="main", folder="dugong_sync")
    writes: list[tuple[str, str, str | None, str]] = []

    monkeypatch.setattr(gt, "_read_remote_file", lambda _path: ('{"a":1}', "sha1"))
    monkeypatch.setattr(gt, "_write_remote_file", lambda path, text, sha, message: writes.append((path, text, sha, message)))

    gt.send({"event_id": "e2"})

    assert len(writes) == 1
    path, text, sha, _msg = writes[0]
    assert path.endswith("cornelius.jsonl")
    assert sha == "sha1"
    assert text.splitlines() == ['{"a":1}', '{"event_id": "e2"}']


def test_github_transport_receive_skips_own_file(monkeypatch) -> None:
    gt = GithubTransport(repo="owner/repo", token="t", source_id="cornelius")

    monkeypatch.setattr(gt, "_list_remote_files", lambda: ["cornelius.jsonl", "anson.jsonl"])
    monkeypatch.setattr(gt, "_read_remote_file", lambda path: ('{"event_id":"x1"}\n{"event_id":"x2"}', "sha") if path.endswith("anson.jsonl") else ("", None))

    payloads = gt.receive()
    ids = [p.get("event_id") for p in payloads]
    assert ids == ["x1", "x2"]


def test_github_transport_receive_incremental_uses_cursor(monkeypatch) -> None:
    gt = GithubTransport(repo="owner/repo", token="t", source_id="cornelius")
    monkeypatch.setattr(gt, "_list_remote_files", lambda: ["anson.jsonl"])
    monkeypatch.setattr(
        gt,
        "_read_remote_file",
        lambda _path: ('{"event_id":"x1"}\n{"event_id":"x2"}\n{"event_id":"x3"}', "sha"),
    )

    payloads, cursors = gt.receive_incremental({"anson.jsonl": 2})
    assert [p.get("event_id") for p in payloads] == ["x3"]
    assert cursors["anson.jsonl"] == 3
