# Dugong v2-m1 (in progress)

Run app:

```bash
python -m dugong_app.main
```

Run tests:

```bash
python -m pytest
```

## Runtime files

- `dugong_state.json` (latest state snapshot)
- `event_journal/` (daily event shards: `YYYY-MM-DD.jsonl`)
- `daily_summary.json` (aggregated behavior summary)
- `focus_sessions.json` (derived study sessions)

## V2 Sync (MVP: file / github transport)

Required env per machine:

- `DUGONG_SOURCE_ID` (example: `cornelius` / `anson`)
- `DUGONG_TRANSPORT=file|github`

If `file`:

- `DUGONG_FILE_TRANSPORT_DIR=<shared_folder_path>`

If `github`:

- `DUGONG_GITHUB_REPO=<owner/repo>`
- `DUGONG_GITHUB_TOKEN=<personal_access_token>`
- `DUGONG_GITHUB_BRANCH=main` (optional)
- `DUGONG_GITHUB_FOLDER=dugong_sync` (optional)

Optional env:

- `DUGONG_TICK_SECONDS` (default `60`)
- `DUGONG_SYNC_INTERVAL_SECONDS` (default `60`)
- `DUGONG_JOURNAL_RETENTION_DAYS` (default `30`)

## Demo script (2 machines)

1. Set same `DUGONG_FILE_TRANSPORT_DIR` on both machines.
2. Start both apps with different `DUGONG_SOURCE_ID`.
3. On A click `ping`.
4. Within one sync interval, B should show remote bubble and `R:<count>` increment.
5. Click B window once to clear unread (`R:0`).

GitHub mode demo:

1. Set same repo/token permissions and same `DUGONG_GITHUB_FOLDER`.
2. Use different `DUGONG_SOURCE_ID` on A/B.
3. A clicks `ping`; B should reflect within one sync interval.
