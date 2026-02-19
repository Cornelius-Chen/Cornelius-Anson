from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


def _default_data_dir(repo_root: Path) -> Path:
    override = os.getenv("DUGONG_DATA_DIR", "").strip()
    if override:
        return Path(override)

    system = platform.system().lower()
    if system == "windows":
        appdata = os.getenv("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / "dugong"
    home = Path.home()
    return home / ".dugong"


@dataclass(frozen=True)
class DugongConfig:
    source_id: str
    skin_id: str
    transport: str
    tick_seconds: int
    sync_interval_seconds: int
    sync_idle_max_multiplier: int
    journal_retention_days: int
    journal_fsync: bool
    derived_rebuild_seconds: int
    data_dir: Path
    file_transport_dir: Path
    github_repo: str
    github_token: str
    github_branch: str
    github_folder: str

    @classmethod
    def from_env(cls, repo_root: Path) -> "DugongConfig":
        data_dir = _default_data_dir(repo_root)
        source_id = os.getenv("DUGONG_SOURCE_ID", "unknown").strip() or "unknown"
        # "auto" means resolve by source_id from skin_map.json in UI assets.
        skin_id = os.getenv("DUGONG_SKIN_ID", "auto").strip() or "auto"
        transport = os.getenv("DUGONG_TRANSPORT", "file").strip().lower() or "file"
        file_transport_default = data_dir / "transport_shared"
        file_transport_dir = Path(os.getenv("DUGONG_FILE_TRANSPORT_DIR", str(file_transport_default)))
        journal_fsync_raw = os.getenv("DUGONG_JOURNAL_FSYNC", "0").strip().lower()
        journal_fsync = journal_fsync_raw in {"1", "true", "yes", "on"}

        return cls(
            source_id=source_id,
            skin_id=skin_id,
            transport=transport,
            tick_seconds=max(1, _env_int("DUGONG_TICK_SECONDS", 60)),
            sync_interval_seconds=max(1, _env_int("DUGONG_SYNC_INTERVAL_SECONDS", 10)),
            sync_idle_max_multiplier=max(1, _env_int("DUGONG_SYNC_IDLE_MAX_MULTIPLIER", 6)),
            journal_retention_days=max(1, _env_int("DUGONG_JOURNAL_RETENTION_DAYS", 30)),
            journal_fsync=journal_fsync,
            derived_rebuild_seconds=max(1, _env_int("DUGONG_DERIVED_REBUILD_SECONDS", 5)),
            data_dir=data_dir,
            file_transport_dir=file_transport_dir,
            github_repo=os.getenv("DUGONG_GITHUB_REPO", "").strip(),
            github_token=os.getenv("DUGONG_GITHUB_TOKEN", "").strip(),
            github_branch=os.getenv("DUGONG_GITHUB_BRANCH", "main").strip() or "main",
            github_folder=os.getenv("DUGONG_GITHUB_FOLDER", "dugong_sync").strip() or "dugong_sync",
        )
