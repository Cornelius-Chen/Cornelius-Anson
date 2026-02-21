from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dugong_app.config import DugongConfig
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.pomodoro_state_json import PomodoroStateStorage
from dugong_app.persistence.reward_state_json import RewardStateStorage
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
        "pomo_focus_minutes": cfg.pomo_focus_minutes,
        "pomo_break_minutes": cfg.pomo_break_minutes,
        "reward_base_pearls": cfg.reward_base_pearls,
        "reward_valid_ratio_percent": cfg.reward_valid_ratio_percent,
        "cofocus_milestone_seconds": cfg.cofocus_milestone_seconds,
        "cofocus_bonus_pearls": cfg.cofocus_bonus_pearls,
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


def _collect_pomo_payload() -> dict:
    data_root = _default_data_root()
    pomo = PomodoroStateStorage(data_root / "pomodoro_state.json").load()
    reward = RewardStateStorage(data_root / "reward_state.json").load()
    return {
        "pomodoro": {
            "state": pomo.get("state", "IDLE"),
            "phase": pomo.get("phase", ""),
            "remaining_s": int(pomo.get("remaining_s", 0)),
            "phase_duration_s": int(pomo.get("phase_duration_s", 0)),
            "session_id": pomo.get("session_id", ""),
            "ends_at_wall": pomo.get("ends_at_wall", 0),
            "focus_minutes": int(pomo.get("focus_minutes", 25)),
            "break_minutes": int(
                pomo.get("break_minutes", 5),
            ),
        },
        "reward": {
            "pearls": int(reward.get("pearls", 0)),
            "lifetime_pearls": int(reward.get("lifetime_pearls", 0)),
            "today_pearls": int(reward.get("today_pearls", 0)),
            "exp": int(reward.get("exp", 0)),
            "lifetime_exp": int(reward.get("lifetime_exp", 0)),
            "today_exp": int(reward.get("today_exp", 0)),
            "level": int(reward.get("level", 1)),
            "exp_in_level": int(reward.get("exp_in_level", 0)),
            "exp_to_next": int(reward.get("exp_to_next", 50)),
            "focus_streak": int(reward.get("focus_streak", 0)),
            "day_streak": int(reward.get("day_streak", 0)),
            "last_focus_day": reward.get("last_focus_day", ""),
            "cofocus_seconds_total": int(reward.get("cofocus_seconds_total", 0)),
            "equipped_skin_id": reward.get("equipped_skin_id", "default"),
            "equipped_bubble_style": reward.get("equipped_bubble_style", "default"),
            "equipped_title_id": reward.get("equipped_title_id", "drifter"),
            "granted_cofocus_milestones_count": len(reward.get("granted_cofocus_milestones", []))
            if isinstance(reward.get("granted_cofocus_milestones", []), list)
            else 0,
            "granted_sessions_count": len(reward.get("granted_sessions", []))
            if isinstance(reward.get("granted_sessions", []), list)
            else 0,
        },
    }


def _cmd_pomo(_args: argparse.Namespace) -> int:
    watch = bool(getattr(_args, "watch", False))
    interval = max(0.1, float(getattr(_args, "interval", 1.0)))
    iterations = int(getattr(_args, "iterations", 0))

    if not watch:
        print(json.dumps(_collect_pomo_payload(), ensure_ascii=False, indent=2))
        return 0

    count = 0
    try:
        while True:
            payload = _collect_pomo_payload()
            print(json.dumps(payload, ensure_ascii=False))
            count += 1
            if iterations > 0 and count >= iterations:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
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

    p_pomo = subparsers.add_parser("pomo", help="Show pomodoro and reward snapshot")
    p_pomo.add_argument("--watch", action="store_true", help="stream snapshot repeatedly")
    p_pomo.add_argument("--interval", type=float, default=1.0, help="watch interval in seconds")
    p_pomo.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="watch loop count (0 = infinite; useful for tests)",
    )
    p_pomo.set_defaults(func=_cmd_pomo)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
