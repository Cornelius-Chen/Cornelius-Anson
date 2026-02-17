from dugong_app.core.events import DugongEvent
from dugong_app.interaction.protocol import PROTOCOL_VERSION, decode_event, encode_event


def test_protocol_roundtrip_v11_fields() -> None:
    event = DugongEvent(
        event_type="mode_change",
        timestamp="2026-02-17T00:00:00+00:00",
        event_id="evt123",
        source="dugong_ui",
        schema_version="v1.1",
        payload={"mode": "study"},
    )
    encoded = encode_event(sender="cornelius", receiver="anson", event=event)

    assert encoded["version"] == PROTOCOL_VERSION
    assert encoded["sender"] == "cornelius"
    assert encoded["receiver"] == "anson"
    assert encoded["event_id"] == "evt123"
    assert encoded["source"] == "dugong_ui"
    assert encoded["schema_version"] == "v1.1"

    decoded = decode_event(encoded)
    assert decoded.event_type == "mode_change"
    assert decoded.payload["mode"] == "study"
    assert decoded.event_id == "evt123"


def test_protocol_decode_backward_compatible_v1_payload() -> None:
    legacy_payload = {
        "version": "v1",
        "sender": "cornelius",
        "receiver": "anson",
        "event": {
            "event_type": "click",
            "timestamp": "2026-02-17T00:00:00+00:00",
            "payload": {},
        },
    }

    decoded = decode_event(legacy_payload)
    assert decoded.event_type == "click"
    assert decoded.schema_version == "v1"
