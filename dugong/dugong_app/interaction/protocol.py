from __future__ import annotations

from dataclasses import asdict, dataclass

from dugong_app.core.events import DugongEvent


@dataclass(frozen=True)
class ProtocolEnvelope:
    version: str
    sender: str
    receiver: str
    event: dict
    event_id: str
    source: str
    schema_version: str


PROTOCOL_VERSION = "v1.2"
SUPPORTED_SCHEMA_VERSIONS = {"v1", "v1.1", "v1.2"}


def encode_event(sender: str, receiver: str, event: DugongEvent) -> dict:
    envelope = ProtocolEnvelope(
        version=PROTOCOL_VERSION,
        sender=sender,
        receiver=receiver,
        event=event.to_dict(),
        event_id=event.event_id,
        source=event.source,
        schema_version=event.schema_version,
    )
    return asdict(envelope)


def decode_event(payload: dict) -> DugongEvent:
    event_payload = payload.get("event")
    if not isinstance(event_payload, dict):
        event_payload = payload

    envelope_version = str(payload.get("version", "v1"))
    schema_version = str(
        event_payload.get(
            "schema_version",
            payload.get("schema_version", envelope_version),
        )
    )
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        schema_version = "v1.2"

    raw_payload = event_payload.get("payload", {})
    event_data = raw_payload if isinstance(raw_payload, dict) else {}

    return DugongEvent(
        event_type=event_payload.get("event_type", "unknown"),
        timestamp=event_payload.get("timestamp", ""),
        event_id=event_payload.get("event_id", payload.get("event_id", "")),
        source=event_payload.get("source", payload.get("source", "unknown")),
        schema_version=schema_version,
        payload=event_data,
    )
