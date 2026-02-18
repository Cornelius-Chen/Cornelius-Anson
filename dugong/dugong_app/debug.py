from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dugong_app.config import DugongConfig
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.runtime_health_json import RuntimeHealthStorage
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage
from dugong_app.services.daily_summary import summarize_events
from dugong_app.services.journal_compaction import compact_daily_journal


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_data_root() -> Path:
    return DugongConfig.from_env(_default_repo_root()).data_dir


def _cmd_last_events(args: argparse.Namespace) -> int:
    journal = EventJournal(_default_data_root() / "event_journal.jsonl")
    events = journal.load_all()
    for event in events[-args.n :]:
        print(f"{event.timestamp} | {event.event_type:12s} | {event.source:10s} | {event.event_id}")
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    journal = EventJournal(_default_data_root() / "event_journal.jsonl")
    events = journal.load_all()
    bad_lines = journal.last_read_stats().get("bad_lines_skipped", 0)
    summary = summarize_events(events)

    if args.today:
        today = datetime.now(tz=timezone.utc).date().isoformat()
        day = next((d for d in summary.get("days", []) if d.get("date") == today), None)
        if day is None:
            print(f"{today}: no events")
            return 0
        print(
            f"{today}: focus_seconds={day.get('focus_seconds', 0)} "
            f"ticks={day.get('ticks', 0)} mode_changes={day.get('mode_changes', 0)} "
            f"manual_pings={day.get('manual_pings', 0)} bad_lines_skipped={bad_lines}"
        )
        return 0

    print(f"generated_at={summary.get('generated_at', '')}")
    print(f"current_streak_days={summary.get('current_streak_days', 0)}")
    print(f"bad_lines_skipped={bad_lines}")
    for day in summary.get("days", []):
        print(
            f"{day.get('date')} focus_seconds={day.get('focus_seconds', 0)} "
            f"ticks={day.get('ticks', 0)} manual_pings={day.get('manual_pings', 0)}"
        )
    return 0


def _cmd_compact_journal(args: argparse.Namespace) -> int:
    journal_dir = _default_data_root() / "event_journal"
    result = compact_daily_journal(journal_dir=journal_dir, keep_days=args.keep_days, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "apply"
    print(
        f"{mode}: scanned_days={result['scanned_days']} "
        f"compacted_days={result['compacted_days']} saved_lines={result['saved_lines']}"
    )
    return 0


def _cmd_config(_args: argparse.Namespace) -> int:
    cfg = DugongConfig.from_env(_default_repo_root())
    payload = {
        "source_id": cfg.source_id,
        "transport": cfg.transport,
        "tick_seconds": cfg.tick_seconds,
        "sync_interval_seconds": cfg.sync_interval_seconds,
        "sync_idle_max_multiplier": cfg.sync_idle_max_multiplier,
        "journal_retention_days": cfg.journal_retention_days,
        "journal_fsync": cfg.journal_fsync,
        "derived_rebuild_seconds": cfg.derived_rebuild_seconds,
        "data_dir": str(cfg.data_dir),
        "file_transport_dir": str(cfg.file_transport_dir),
        "github_repo": cfg.github_repo,
        "github_branch": cfg.github_branch,
        "github_folder": cfg.github_folder,
        "github_token": "***" if cfg.github_token else "",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_health(_args: argparse.Namespace) -> int:
    data_root = _default_data_root()
    health = RuntimeHealthStorage(data_root / "sync_health.json").load()
    cursor = SyncCursorStorage(data_root / "sync_cursor.json").load()

    journal = EventJournal(data_root / "event_journal.jsonl")
    journal.load_all()
    bad_lines = journal.last_read_stats().get("bad_lines_skipped", 0)

    payload = {
        "sync_state": health.get("sync_state", "unknown"),
        "paused_reason": health.get("paused_reason", ""),
        "unread_remote_count": health.get("unread_remote_count", 0),
        "bad_lines_skipped": bad_lines,
        "cursor_last_seen_event_id_by_source": cursor.get("last_seen_event_id_by_source", {}),
        "cursor_last_seen_timestamp_by_source": cursor.get("last_seen_timestamp_by_source", {}),
        "last_push_at": health.get("last_push_at", ""),
        "last_push_count": health.get("last_push_count", 0),
        "last_pull_at": health.get("last_pull_at", ""),
        "last_pull_imported": health.get("last_pull_imported", 0),
        "last_pull_received": health.get("last_pull_received", 0),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m dugong_app.debug")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_last = subparsers.add_parser("last-events", help="Show recent events")
    p_last.add_argument("--n", type=int, default=20)
    p_last.set_defaults(func=_cmd_last_events)

    p_summary = subparsers.add_parser("summary", help="Show summary")
    p_summary.add_argument("--today", action="store_true")
    p_summary.set_defaults(func=_cmd_summary)

    p_compact = subparsers.add_parser("compact-journal", help="Roll up old daily journal files")
    p_compact.add_argument("--keep-days", type=int, default=7)
    p_compact.add_argument("--dry-run", action="store_true")
    p_compact.set_defaults(func=_cmd_compact_journal)

    p_config = subparsers.add_parser("config", help="Show effective config (token masked)")
    p_config.set_defaults(func=_cmd_config)

    p_health = subparsers.add_parser("health", help="Show backend health snapshot")
    p_health.set_defaults(func=_cmd_health)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
