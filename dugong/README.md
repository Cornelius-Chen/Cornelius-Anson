# Dugong v1.2-core

Run desktop pet app:

```bash
python -m dugong_app.main
```

Run tests:

```bash
python -m pytest
```

Runtime files (auto-generated in `dugong/`):

- `dugong_state.json` (latest state snapshot)
- `event_journal/` (daily event shards: `YYYY-MM-DD.jsonl`)
- `daily_summary.json` (aggregated behavior summary)

Backward compatibility:

- Existing `event_journal.jsonl` is still readable.

Optional env:

- `DUGONG_TICK_SECONDS` (default `60`)
- `DUGONG_JOURNAL_RETENTION_DAYS` (default `30`)
