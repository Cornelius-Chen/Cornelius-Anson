# Dugong v2-m1 (in progress)

Run app:

```bash
python -m dugong_app.main
```

Run tests:

```bash
python -m pytest
```

Debug CLI:

```bash
python -m dugong_app.debug last-events --n 20
python -m dugong_app.debug summary --today
python -m dugong_app.debug config
python -m dugong_app.debug health
python -m dugong_app.debug pomo
python -m dugong_app.debug pomo --watch --interval 0.5
python -m dugong_app.debug compact-journal --keep-days 7 --dry-run
python -m dugong_app.debug compact-journal --keep-days 7
```

Stability harness:

```bash
python scripts/stress_sync.py --clean --hours 24
# quick smoke:
python scripts/stress_sync.py --clean --hours 0.01

# pomodoro black-box (fast)
python scripts/stress_pomo.py --mode fast --minutes 3 --seed 42 --clean

# pomodoro long soak
python scripts/stress_pomo.py --mode soak --hours 2 --restart-rate 0.02 --net-jitter 0.1 --clean
```

V2 demo helper (5-minute script):

```bash
# print fixed timeline + env blocks for A/B
python scripts/demo_v2.py --transport github --repo owner/repo --include-cofocus

# run real-time timeline countdown
python scripts/demo_v2.py --transport github --repo owner/repo --include-cofocus --run
```

Sprite prep pipeline (AnimateDiff/Runway output -> PNG frames):

```bash
# from a folder of extracted images:
python scripts/prepare_sprites.py --input ./raw_frames --output ./dugong_app/ui/assets --count 8 --prefix dugong_swim_right --bg-key 00ff00 --mirror

# from a GIF/WebP animation:
python scripts/prepare_sprites.py --input ./dugong_loop.gif --output ./dugong_app/ui/assets --count 8 --prefix dugong_idle_right --bg-key 00ff00 --mirror
```

## Runtime files

- Data root defaults:
  - Windows: `%APPDATA%\\dugong`
  - macOS/Linux: `~/.dugong`
  - Override with: `DUGONG_DATA_DIR`
  - Startup will auto-migrate legacy runtime files from repo root into data root (copy-only, non-destructive).
- Runtime files under data root:
  - `dugong_state.json` (latest state snapshot)
  - `event_journal/` (daily event shards: `YYYY-MM-DD.jsonl`)
  - `daily_summary.json` (aggregated behavior summary)
  - `focus_sessions.json` (derived study sessions)
  - `sync_cursor.json` (per-remote file cursor for incremental sync)
  - `sync_health.json` (backend health snapshot for debug CLI)

Schema compatibility notes: `docs/schema_migrations.md`

## V2 Sync (MVP: file / github transport)

Required env per machine:

- `DUGONG_SOURCE_ID` (example: `cornelius` / `anson`)
- `DUGONG_TRANSPORT=file|github`
- `DUGONG_DATA_DIR` (optional, override default data root)

If `file`:

- `DUGONG_FILE_TRANSPORT_DIR=<shared_folder_path>`

If `github`:

- `DUGONG_GITHUB_REPO=<owner/repo>`
- `DUGONG_GITHUB_TOKEN=<personal_access_token>`
- `DUGONG_GITHUB_BRANCH=main` (optional)
- `DUGONG_GITHUB_FOLDER=dugong_sync` (optional)

Optional env:

- `DUGONG_TICK_SECONDS` (default `60`)
- `DUGONG_SYNC_INTERVAL_SECONDS` (default `10`)
- `DUGONG_SYNC_IDLE_MAX_MULTIPLIER` (default `6`, adaptive idle sync backoff)
- `DUGONG_JOURNAL_RETENTION_DAYS` (default `30`)
- `DUGONG_DERIVED_REBUILD_SECONDS` (default `5`)
- `DUGONG_JOURNAL_FSYNC=1` (enable fsync on journal append)
- `DUGONG_POMO_FOCUS_MINUTES` (default `25`)
- `DUGONG_POMO_BREAK_MINUTES` (default `5`)
- `DUGONG_REWARD_BASE_PEARLS` (default `10`)
- `DUGONG_REWARD_VALID_RATIO_PERCENT` (default `80`, reward threshold)
- `DUGONG_COFOCUS_MILESTONE_SECONDS` (default `600`)
- `DUGONG_COFOCUS_BONUS_PEARLS` (default `5`)

## Pomodoro V1 (manual-start anti-AFK)

- Rules:
  - `IDLE -> FOCUS` only by manual click (`pomo` button).
  - `FOCUS -> BREAK` auto switch.
  - `BREAK -> next FOCUS` requires manual click (`pomo` button again).
  - Restart/crash recovery restores Pomodoro as `PAUSED` (never auto-runs).
- UI controls:
  - `pomo`: start focus
  - `pause`: pause/resume current Pomodoro phase
  - `skip`: skip current phase
- Reward:
  - valid focus completion grants pearls (`base + streak bonus`)
  - grant is idempotent by `session_id` (replay-safe)
- New runtime files:
  - `pomodoro_state.json`
  - `reward_state.json`
- Synced high-value events:
  - `pomo_start`, `pomo_pause`, `pomo_resume`, `pomo_skip`, `pomo_complete`, `reward_grant`
  - `co_focus_milestone` (when local+remote focus overlap reaches milestone)

## Demo script (2 machines)

1. Set same `DUGONG_FILE_TRANSPORT_DIR` on both machines.
2. Start both apps with different `DUGONG_SOURCE_ID`.
3. On A click `ping`.
4. Within one sync interval, B should show remote bubble reaction.

GitHub mode demo:

1. Set same repo/token permissions and same `DUGONG_GITHUB_FOLDER`.
2. Use different `DUGONG_SOURCE_ID` on A/B.
3. A clicks `ping`; B should reflect within one sync interval.

