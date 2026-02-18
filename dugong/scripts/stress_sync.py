from __future__ import annotations

import argparse
import random
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dugong_app.core.events import DugongEvent, manual_ping_event, mode_change_event
from dugong_app.interaction.protocol import encode_event
from dugong_app.interaction.transport_base import TransportBase
from dugong_app.interaction.transport_file import FileTransport
from dugong_app.persistence.event_journal import EventJournal
from dugong_app.persistence.sync_cursor_json import SyncCursorStorage
from dugong_app.services.journal_compaction import compact_daily_journal
from dugong_app.services.sync_engine import SyncEngine


class SimulatedNetworkError(RuntimeError):
    pass


@dataclass
class FaultConfig:
    random_error_rate: float
    auth_fail_start_sec: int
    auth_fail_end_sec: int
    rate_limit_start_sec: int
    rate_limit_end_sec: int


class FlakyTransport(TransportBase):
    def __init__(self, inner: FileTransport, fault: FaultConfig, started_at: float) -> None:
        self.inner = inner
        self.fault = fault
        self.started_at = started_at

    def send(self, payload: dict) -> None:
        self._maybe_raise()
        self.inner.send(payload)

    def receive(self) -> list[dict]:
        self._maybe_raise()
        return self.inner.receive()

    def receive_incremental(self, cursors: dict[str, int] | None = None) -> tuple[list[dict], dict[str, int]]:
        self._maybe_raise()
        return self.inner.receive_incremental(cursors)

    def _maybe_raise(self) -> None:
        elapsed = int(time.monotonic() - self.started_at)
        if self.fault.auth_fail_start_sec <= elapsed <= self.fault.auth_fail_end_sec:
            raise RuntimeError("github read failed: status=401")
        if self.fault.rate_limit_start_sec <= elapsed <= self.fault.rate_limit_end_sec:
            raise RuntimeError("github read failed: status=429 rate_limit_reset=9999999999")
        if random.random() < self.fault.random_error_rate:
            raise SimulatedNetworkError("simulated network glitch")


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _render_progress(now: float, started: float, stop_at: float, counters: dict[str, int]) -> None:
    total = max(1e-6, stop_at - started)
    elapsed = max(0.0, now - started)
    ratio = min(1.0, elapsed / total)
    width = 30
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    line = (
        f"\r[{bar}] {ratio*100:6.2f}% "
        f"elapsed={elapsed:7.1f}s "
        f"sync_fail={counters.get('sync_failures', 0)} "
        f"paused={counters.get('sync_paused', 0)} "
        f"sent={counters.get('local_events_sent', 0)}"
    )
    print(line, end="", flush=True)


def make_engine(workdir: Path, source: str, shared_dir: Path, fault: FaultConfig, started_at: float) -> SyncEngine:
    journal = EventJournal(workdir / source / "event_journal.jsonl", retention_days=30, fsync_writes=False)
    cursor = SyncCursorStorage(workdir / source / "sync_cursor.json")
    base = FileTransport(shared_dir=shared_dir, source_id=source)
    flaky = FlakyTransport(base, fault=fault, started_at=started_at)
    return SyncEngine(source_id=source, journal=journal, transport=flaky, cursor_storage=cursor)


def run_stability_harness(args: argparse.Namespace) -> int:
    random.seed(args.seed)
    workdir = Path(args.workdir).resolve()
    if args.clean and workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    shared = workdir / "shared"
    shared.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    fault = FaultConfig(
        random_error_rate=args.random_error_rate,
        auth_fail_start_sec=args.auth_fail_start_sec,
        auth_fail_end_sec=args.auth_fail_end_sec,
        rate_limit_start_sec=args.rate_limit_start_sec,
        rate_limit_end_sec=args.rate_limit_end_sec,
    )
    a_engine = make_engine(workdir, "cornelius", shared, fault, started)
    b_engine = make_engine(workdir, "anson", shared, fault, started)

    modes = ["study", "chill", "rest"]
    counters = {
        "local_events_sent": 0,
        "forced_syncs": 0,
        "sync_failures": 0,
        "sync_paused": 0,
        "rollup_compactions": 0,
        "rollup_crash_simulated": 0,
        "schema_mismatch_sent": 0,
    }

    next_ping = 0.0
    next_mode = 0.0
    next_sync = 0.0
    next_compact = 0.0
    stop_at = started + int(args.hours * 3600)

    while time.monotonic() < stop_at:
        now = time.monotonic()

        if now >= next_ping:
            src = random.choice(["cornelius", "anson"])
            event = manual_ping_event("stress_ping", source=src)
            (a_engine if src == "cornelius" else b_engine).journal.append(event)
            try:
                (a_engine if src == "cornelius" else b_engine).publish_local_event(event)
            except Exception:
                pass
            counters["local_events_sent"] += 1
            next_ping = now + args.ping_every_seconds

        if now >= next_mode:
            src = random.choice(["cornelius", "anson"])
            event = mode_change_event(random.choice(modes), source=src)
            (a_engine if src == "cornelius" else b_engine).journal.append(event)
            try:
                (a_engine if src == "cornelius" else b_engine).publish_local_event(event)
            except Exception:
                pass
            counters["local_events_sent"] += 1
            next_mode = now + args.mode_every_seconds

        if now >= next_sync:
            for engine in (a_engine, b_engine):
                result = engine.sync_once(force=True)
                counters["forced_syncs"] += 1
                status = str(result.get("status", ""))
                if status == "paused":
                    counters["sync_paused"] += 1
                if status not in {"ok", "disabled"}:
                    counters["sync_failures"] += 1
            next_sync = now + args.sync_every_seconds

        # simulate version mismatch payloads (unknown schema version)
        if random.random() < args.schema_mismatch_rate:
            raw = DugongEvent(
                event_type="manual_ping",
                timestamp=now_iso(),
                event_id=f"mismatch-{int(now*1000)}",
                source="cornelius",
                schema_version="v9",
                payload={"message": "mismatch"},
            )
            encoded = encode_event(sender="cornelius", receiver="*", event=raw)
            try:
                a_engine.transport.send(encoded)  # type: ignore[union-attr]
            except Exception:
                pass
            counters["schema_mismatch_sent"] += 1

        if now >= next_compact:
            for root in (workdir / "cornelius" / "event_journal", workdir / "anson" / "event_journal"):
                if random.random() < args.compaction_crash_rate:
                    counters["rollup_crash_simulated"] += 1
                    # Crash simulation: skip applying compaction this round.
                    continue
                result = compact_daily_journal(root, keep_days=args.compact_keep_days, dry_run=False)
                counters["rollup_compactions"] += int(result.get("compacted_days", 0))
            next_compact = now + args.compact_every_seconds

        _render_progress(now=now, started=started, stop_at=stop_at, counters=counters)
        time.sleep(0.2)

    print()
    summary = {
        "workdir": str(workdir),
        "runtime_hours": args.hours,
        "counters": counters,
        "a_status": a_engine.last_status,
        "b_status": b_engine.last_status,
    }
    print(summary)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dugong sync stability harness")
    parser.add_argument("--workdir", default=".stress_sync")
    parser.add_argument("--hours", type=float, default=0.1, help="Run duration in hours")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clean", action="store_true")

    parser.add_argument("--ping-every-seconds", type=int, default=5)
    parser.add_argument("--mode-every-seconds", type=int, default=20)
    parser.add_argument("--sync-every-seconds", type=int, default=60)
    parser.add_argument("--compact-every-seconds", type=int, default=300)
    parser.add_argument("--compact-keep-days", type=int, default=1)

    parser.add_argument("--random-error-rate", type=float, default=0.05)
    parser.add_argument("--schema-mismatch-rate", type=float, default=0.01)
    parser.add_argument("--compaction-crash-rate", type=float, default=0.05)

    parser.add_argument("--auth-fail-start-sec", type=int, default=600)
    parser.add_argument("--auth-fail-end-sec", type=int, default=900)
    parser.add_argument("--rate-limit-start-sec", type=int, default=1200)
    parser.add_argument("--rate-limit-end-sec", type=int, default=1500)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_stability_harness(parse_args()))
