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
python -m dugong_app.debug compact-journal --keep-days 7 --dry-run
python -m dugong_app.debug compact-journal --keep-days 7
```

Stability harness:

```bash
python scripts/stress_sync.py --clean --hours 24
# quick smoke:
python scripts/stress_sync.py --clean --hours 0.01
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

## Demo script (2 machines)

1. Set same `DUGONG_FILE_TRANSPORT_DIR` on both machines.
2. Start both apps with different `DUGONG_SOURCE_ID`.
3. On A click `ping`.
4. Within one sync interval, B should show remote bubble reaction.

GitHub mode demo:

1. Set same repo/token permissions and same `DUGONG_GITHUB_FOLDER`.
2. Use different `DUGONG_SOURCE_ID` on A/B.
3. A clicks `ping`; B should reflect within one sync interval.

