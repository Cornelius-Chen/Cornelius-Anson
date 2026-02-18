import json

from dugong_app.interaction.transport_file import FileTransport


def test_file_transport_receive_incremental_uses_cursor(tmp_path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    remote = shared / "anson.jsonl"
    remote.write_text(
        "\n".join(
            [
                json.dumps({"event_id": "e1"}),
                json.dumps({"event_id": "e2"}),
                json.dumps({"event_id": "e3"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    transport = FileTransport(shared_dir=shared, source_id="cornelius")
    payloads, cursors = transport.receive_incremental({"anson.jsonl": 2})
    assert [p.get("event_id") for p in payloads] == ["e3"]
    assert cursors["anson.jsonl"] == 3
