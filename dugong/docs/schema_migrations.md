# Schema Migrations

This document defines backward-compatibility expectations for event decoding.

## Versions

- `v1`
  - Early payloads may not contain `schema_version`.
  - Decoder falls back to envelope `version` or defaults to `v1`.
- `v1.1`
  - Adds stable `event_id` usage and sender/source fields in envelopes.
  - Decoder still accepts missing optional fields and fills defaults.
- `v1.2`
  - Current target.
  - Decoder enforces `payload` as object; non-object payloads become `{}`.
  - Unknown schema versions are coerced to `v1.2` decode defaults.

## Compatibility Matrix

- `v1` payload -> `v1.2` decoder: supported
- `v1.1` payload -> `v1.2` decoder: supported
- `v1.2` payload -> `v1.2` decoder: supported

## Rules for Future Changes

- Never remove `event_id`, `event_type`, `timestamp`, `source`.
- Any new field must be optional and have a decoder default.
- Decoder must continue to accept older payloads without crashing.
