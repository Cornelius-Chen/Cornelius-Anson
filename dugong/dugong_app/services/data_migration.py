from __future__ import annotations

import shutil
from pathlib import Path


RUNTIME_FILES = [
    "dugong_state.json",
    "daily_summary.json",
    "focus_sessions.json",
    "sync_cursor.json",
    "sync_health.json",
]
RUNTIME_DIRS = [
    "event_journal",
    "transport_shared",
]


def migrate_legacy_repo_data(repo_root: Path, data_dir: Path) -> dict[str, int]:
    repo_root = Path(repo_root)
    data_dir = Path(data_dir)
    if repo_root.resolve() == data_dir.resolve():
        return {"migrated_files": 0, "migrated_dirs": 0}

    migrated_files = 0
    migrated_dirs = 0
    data_dir.mkdir(parents=True, exist_ok=True)

    for name in RUNTIME_FILES:
        src = repo_root / name
        dst = data_dir / name
        if src.exists() and src.is_file() and not dst.exists():
            shutil.copy2(src, dst)
            migrated_files += 1

    for name in RUNTIME_DIRS:
        src = repo_root / name
        dst = data_dir / name
        if src.exists() and src.is_dir() and not dst.exists():
            shutil.copytree(src, dst)
            migrated_dirs += 1

    return {"migrated_files": migrated_files, "migrated_dirs": migrated_dirs}
