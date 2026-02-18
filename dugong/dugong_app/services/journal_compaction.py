from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from dugong_app.core.events import DugongEvent
from dugong_app.services.daily_summary import summarize_events


def _safe_event_from_payload(payload: dict) -> DugongEvent:
    return DugongEvent(
        event_type=payload.get("event_type", "unknown"),
        timestamp=payload.get("timestamp", ""),
        event_id=payload.get("event_id", ""),
        source=payload.get("source", "dugong_app"),
        schema_version=payload.get("schema_version", "v1.1"),
        payload=payload.get("payload", {}) if isinstance(payload.get("payload", {}), dict) else {},
    )


def _read_events(file_path: Path) -> list[DugongEvent]:
    events: list[DugongEvent] = []
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    events.append(_safe_event_from_payload(payload))
    except OSError:
        return []
    return events


def _rollup_event_for_day(day: str, events: list[DugongEvent]) -> DugongEvent:
    summary = summarize_events(events)
    day_payload = next((d for d in summary.get("days", []) if d.get("date") == day), None)
    if day_payload is None:
        day_payload = {
            "focus_seconds": 0,
            "ticks": 0,
            "mode_changes": 0,
            "clicks": 0,
            "manual_pings": 0,
        }

    source_candidates = {e.source for e in events if e.source}
    rolled_up_source = source_candidates.pop() if len(source_candidates) == 1 else "mixed"
    payload = {
        "date": day,
        "focus_seconds": int(day_payload.get("focus_seconds", 0)),
        "ticks": int(day_payload.get("ticks", 0)),
        "mode_changes": int(day_payload.get("mode_changes", 0)),
        "clicks": int(day_payload.get("clicks", 0)),
        "manual_pings": int(day_payload.get("manual_pings", 0)),
        "rolled_up_event_count": len(events),
        "rolled_up_from_dates": [day],
        "rolled_up_source": rolled_up_source,
        "rollup_version": "v1",
        "compaction_version": "v1",
    }
    return DugongEvent(
        event_type="daily_rollup",
        timestamp=f"{day}T23:59:59+00:00",
        event_id=f"rollup-{day}",
        source="dugong_rollup",
        schema_version="v1.2",
        payload=payload,
    )


def _write_single_event(file_path: Path, event: DugongEvent) -> None:
    line = json.dumps(event.to_dict(), ensure_ascii=True) + "\n"
    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(file_path.parent)) as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_path = Path(handle.name)
    os.replace(tmp_path, file_path)


def compact_daily_journal(journal_dir: Path, keep_days: int = 7, dry_run: bool = False) -> dict[str, int]:
    keep_days = max(1, int(keep_days))
    journal_dir = Path(journal_dir)
    if not journal_dir.exists():
        return {"scanned_days": 0, "compacted_days": 0, "saved_lines": 0}

    cutoff = datetime.now(tz=timezone.utc).date() - timedelta(days=keep_days - 1)
    scanned_days = 0
    compacted_days = 0
    saved_lines = 0

    for file_path in sorted(journal_dir.glob("*.jsonl")):
        try:
            day = date.fromisoformat(file_path.stem)
        except ValueError:
            continue
        if day >= cutoff:
            continue

        scanned_days += 1
        events = _read_events(file_path)
        if not events:
            continue
        if _is_already_compacted(day.isoformat(), events):
            continue

        rollup = _rollup_event_for_day(day.isoformat(), events)
        if not dry_run:
            _write_single_event(file_path, rollup)

        compacted_days += 1
        saved_lines += max(0, len(events) - 1)

    return {
        "scanned_days": scanned_days,
        "compacted_days": compacted_days,
        "saved_lines": saved_lines,
    }


def _is_already_compacted(day: str, events: list[DugongEvent]) -> bool:
    if len(events) != 1:
        return False
    event = events[0]
    if event.event_type != "daily_rollup":
        return False
    payload = event.payload if isinstance(event.payload, dict) else {}
    dates = payload.get("rolled_up_from_dates", [])
    if not isinstance(dates, list):
        return False
    return payload.get("compaction_version") == "v1" and day in {str(d) for d in dates}
