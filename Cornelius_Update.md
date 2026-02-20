# Update Log

## 2026-02-17 03:53:07
- Scope: 根据 README 补全 Dugong V1（仓库目录为 `dugong/`）。
- Added/Implemented:
  - 完成核心状态与规则：`dugong/dugong_app/core/state.py`，`dugong/dugong_app/core/rules.py`
  - 完成事件系统：`dugong/dugong_app/core/events.py`，`dugong/dugong_app/core/event_bus.py`
  - 完成 tick 时钟：`dugong/dugong_app/core/clock.py`
  - 完成 JSON 持久化：`dugong/dugong_app/persistence/storage_json.py`
  - 完成协议封装：`dugong/dugong_app/interaction/protocol.py`
  - 完成传输层基类及占位实现：`dugong/dugong_app/interaction/transport_base.py`，`dugong/dugong_app/interaction/transport_file.py`，`dugong/dugong_app/interaction/transport_github.py`，`dugong/dugong_app/interaction/transport_lan.py`
  - 完成 UI 与渲染：`dugong/dugong_app/ui/shell_qt.py`，`dugong/dugong_app/ui/renderer.py`
  - 完成控制器入口：`dugong/dugong_app/main.py`
  - 完成测试：`dugong/tests/test_state_tick.py`，`dugong/tests/test_protocol.py`
  - 更新说明文档：`dugong/README.md`，`dugong/dugong_app/__init__.py`
- Validation:
  - `python -m pytest` -> 4 passed
  - `python -c "from dugong_app.main import create_default_controller; print(type(create_default_controller()).__name__)"` -> `DugongController`

---

## Template
- Time: YYYY-MM-DD HH:MM:SS
- Scope:
- Files:
  - path/to/file
- Changes:
  - ...
- Validation:
  - command -> result

## 2026-02-17 04:00:00
- Scope: 修复 `dugong_app.main` 语法错误（`from __future__` 不在文件顶部）。
- Files:
  - `dugong/dugong_app/main.py`
- Changes:
  - 清理重复拼接内容，恢复为单一、可运行的控制器入口文件。
- Validation:
  - `python -m pytest` -> 4 passed
  - `python -c "import dugong_app.main as m; print('ok', hasattr(m, 'create_default_controller'))"` -> ok True

## 2026-02-17 04:08:00
- Scope: 降低协作冲突，拆分启动入口与控制器实现。
- Files:
  - `dugong/dugong_app/controller.py`
  - `dugong/dugong_app/main.py`
  - `dugong/tests/test_entrypoint.py`
- Changes:
  - 新增 `controller.py`，承载 `DugongController` 和 `create_default_controller()`。
  - `main.py` 精简为纯入口文件，仅负责调用 `create_default_controller().run()`。
  - 新增入口测试，确保 `dugong_app.main` 仍可导入并创建控制器。
- Validation:
  - `python -m pytest` -> 5 passed
  - `python -c "from dugong_app.main import create_default_controller; c=create_default_controller(); print(type(c).__name__)"` -> DugongController

## 2026-02-17 04:13:00
- Scope: 修复 macOS 下右键无法弹出模式菜单的问题。
- Files:
  - `dugong/dugong_app/ui/shell_qt.py`
- Changes:
  - 上下文菜单绑定扩展为 `<Button-2>`、`<Button-3>`、`<Control-Button-1>`，兼容不同 Tk/macOS 事件映射。
  - 将点击/右键绑定覆盖到 `frame/title_label/state_label/bubble_label`，避免点在子控件上无响应。
  - `tk_popup` 后增加 `grab_release()`，避免菜单抓取导致交互异常。
- Validation:
  - `python -m pytest` -> 5 passed

## 2026-02-17 04:26:00
- Scope: 因 UI 未完全实现导致的待办说明（给 Anson）。
- Blocked By UI:
  - 目前只有基础文本 UI，尚未实现 sprite/皮肤资源加载与状态动画切换。
  - 未实现气泡样式分级（按 mode + stat 区分语气/颜色/时长）。
  - 未实现窗口边缘吸附、缩放策略与多分辨率适配。
  - 未实现右键菜单的视觉化（当前为系统原生 menu）。
- Anson Action Plan:
  - 仅修改 `dugong/dugong_app/ui/*`，尽量不改 `dugong/dugong_app/controller.py`。
  - 在 `dugong/dugong_app/ui/renderer.py` 增加：
    - `sprite_for(state)` 返回可映射到 assets 的稳定 key（如 `sleepy/focused/happy/neutral` 细化版）。
    - `bubble_for_click(state)` 按 `mode` 和数值区间返回更细粒度文案与样式 key。
  - 在 `dugong/dugong_app/ui/shell_qt.py` 增加：
    - 资源加载层（从 `ui/assets/` 读取图片/帧）。
    - `update_view` 中根据 sprite key 切图，而不是只改标题文字。
    - 保持现有事件接口不变：`on_mode_change(mode)`、`on_click()`。
- Interface Contract (Do Not Break):
  - `DugongShell(on_mode_change, on_click)`
  - `DugongShell.update_view(sprite: str, state_text: str, bubble: str | None)`
  - `Renderer.sprite_for(state) -> str`
  - `Renderer.bubble_for_click(state) -> str`
- Acceptance:
  - `python -m pytest` 通过。
  - `python -m dugong_app.main` 可启动。
  - 右键可切换 mode；点击有 bubble；不同状态可看到不同 sprite（不再只是文本）。

## 2026-02-17 05:02:00
- Scope: v1.1-core upgrade (behavior history + protocol extensibility + manual signal).
- Files:
  - `dugong/dugong_app/core/events.py`
  - `dugong/dugong_app/interaction/protocol.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/dugong_app/persistence/event_journal.py`
  - `dugong/dugong_app/persistence/summary_json.py`
  - `dugong/dugong_app/services/daily_summary.py`
  - `dugong/tests/test_protocol.py`
  - `dugong/tests/test_event_journal_and_summary.py`
  - `dugong/dugong_app/__init__.py`
  - `dugong/README.md`
- Changes:
  - `DugongEvent` 扩展 `event_id/source/schema_version`，新增 `manual_ping_event`。
  - 协议升级为 `v1.1`：Envelope 增加 `event_id/source/schema_version`，并保持 v1 解码兼容。
  - 新增 `event_journal.jsonl` 事件日志持久化（append-only）。
  - 新增 `daily_summary.json` 聚合（focus_seconds/mode_changes/clicks/manual_pings/current_streak_days）。
  - 控制器在每次事件后自动：保存 state -> 写 journal -> 刷 summary。
  - 控制器新增 `on_manual_ping()`；UI 若支持可直接注入，不支持则自动回退旧 UI 构造方式。
  - 版本号更新：`dugong_app.__version__ = 0.2.0`。
- Validation:
  - `python -m pytest` -> 8 passed
  - `python -c "from dugong_app.main import create_default_controller; c=create_default_controller(); print(type(c).__name__)"` -> DugongController
- UI Follow-up for Anson:
  - 若要在 UI 暴露“手动信号”，在 `DugongShell` 增加一个轻量入口（按钮或快捷键）调用 `on_manual_ping("...")`。
  - 入口是可选增强，不影响 core；当前 controller 已兼容“有/无该回调”两种 UI 版本。

## 2026-02-17 05:12:00
- Scope: v1.1-core 继续推进，打通 UI manual_ping 入口（不破坏旧接口）。
- Files:
  - `dugong/dugong_app/ui/shell_qt.py`
- Changes:
  - `DugongShell.__init__` 增加可选参数 `on_manual_ping`，默认 `None`，保持向后兼容。
  - Hover Action Bar 新增 `ping` 按钮，触发 `on_manual_ping("checkin")`。
  - 右键菜单新增 `manual ping` 项，作为备用入口。
  - 若 UI 未注入该回调则静默忽略，不影响主流程。
- Validation:
  - `python -m pytest` -> 8 passed

## 2026-02-17 05:24:00
- Scope: v1.2-core upgrade (event journal rotation + retention policy).
- Files:
  - `dugong/dugong_app/persistence/event_journal.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/tests/test_event_journal_and_summary.py`
  - `dugong/dugong_app/__init__.py`
  - `dugong/README.md`
- Changes:
  - 事件日志由单文件升级为按日分片目录：`event_journal/YYYY-MM-DD.jsonl`。
  - 新增日志保留策略：仅保留最近 N 天（默认 30 天）。
  - 向后兼容：旧 `event_journal.jsonl` 仍可读取。
  - 控制器新增环境变量读取：`DUGONG_JOURNAL_RETENTION_DAYS`。
  - 新增 retention 测试，验证旧日志自动清理。
  - 版本更新：`0.3.0`。
- Validation:
  - `python -m pytest` -> 9 passed
  - `python -c "from dugong_app.main import create_default_controller; c=create_default_controller(); print(type(c).__name__)"` -> DugongController
- UI Follow-up for Anson:
  - 可选在 UI 提供“最近 N 天日志保留设置”的设置入口（写入 env 或配置文件）。
  - 可选增加一个“summary preview”入口，读取 `daily_summary.json` 展示 streak/今日 focus。

## 2026-02-17 06:05:00
- Scope: v1.3-core upgrade (focus session derivation and persistence).
- Files:
  - `dugong/dugong_app/services/focus_sessions.py`
  - `dugong/dugong_app/persistence/focus_sessions_json.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/tests/test_focus_sessions.py`
  - `dugong/dugong_app/__init__.py`
  - `dugong/README.md`
- Changes:
  - Added focus session builder from event stream (`mode_change` study enter/exit).
  - Added persistence file `focus_sessions.json`.
  - Controller now writes focus sessions on every event update.
  - Version bump to `0.4.0`.
- Validation:
  - `python -m pytest` -> 11 passed
- UI Follow-up for Anson (minimal):
  - Optional only: show `today sessions count` from `focus_sessions.json` in existing bubble or status text.
  - No UI API contract change required.

## 2026-02-17 06:40:00
- Scope: V2 M1 start (file transport + sync engine + remote reflection baseline).
- Files:
  - `dugong/dugong_app/interaction/transport_file.py`
  - `dugong/dugong_app/services/sync_engine.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/dugong_app/core/events.py`
  - `dugong/tests/test_sync_engine.py`
  - `README.md`
  - `dugong/README.md`
- Changes:
  - Implemented `file` transport MVP via shared folder jsonl exchange.
  - Implemented sync engine: publish local events, pull remote events, event_id dedupe, append remote journal.
  - Added V2 config in controller: source_id/transport/sync_interval/shared_dir.
  - Added minimal remote reflection without UI file changes:
    - state line includes `R:<unread_remote>` and `S:<sync_status>`
    - bubble reflects remote `manual_ping`/`mode_change`
    - click clears unread count
  - Event constructors now support explicit `source`.
- Validation:
  - `python -m pytest` -> 12 passed

## 2026-02-17 07:05:00
- Scope: V2 transport extension (GitHub transport beta).
- Files:
  - `dugong/dugong_app/interaction/transport_github.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/tests/test_transport_github.py`
  - `README.md`
  - `dugong/README.md`
- Changes:
  - Implemented GitHub-based transport using repo contents API (append/read jsonl files).
  - Controller now supports `DUGONG_TRANSPORT=github` with env config.
  - Added tests for github transport send/receive behavior (mocked API methods).
  - Updated docs with github setup variables and demo steps.
- Validation:
  - `python -m pytest` -> 14 passed

## 2026-02-17 07:18:00
- Scope: sync responsiveness upgrade (auto-fast + manual sync now).
- Files:
  - `dugong/dugong_app/controller.py`
  - `dugong/dugong_app/ui/shell_qt.py`
  - `dugong/README.md`
- Changes:
  - Default sync interval reduced to 10s (`DUGONG_SYNC_INTERVAL_SECONDS`).
  - Run startup now triggers immediate sync once.
  - Added manual sync entry: option bar `sync` button + context menu `sync now`.
  - Controller added `on_sync_now()` with instant feedback bubble (`Sync now: +N` / `Sync failed`).
- Validation:
  - `python -m pytest` -> 14 passed

## 2026-02-17 08:10:00
- Scope: UI pet animation support (3-frame PNG loop, fallback-safe).
- Files:
  - `dugong/dugong_app/ui/shell_qt.py`
  - `dugong/dugong_app/ui/assets/README.md`
- Changes:
  - Added auto-loading of `seal_1.png`/`seal_2.png`/`seal_3.png` from `ui/assets/`.
  - Added frame loop animation (~140ms per frame).
  - If assets are missing/invalid, UI falls back to emoji (no crash).
- Validation:
  - `python -m pytest` -> 14 passed

## 2026-02-18 18:20:00
- Scope: Backend reliability + smarter sync + safe journal compaction.
- Files:
  - `dugong/dugong_app/config.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/dugong_app/interaction/protocol.py`
  - `dugong/dugong_app/interaction/transport_base.py`
  - `dugong/dugong_app/interaction/transport_file.py`
  - `dugong/dugong_app/interaction/transport_github.py`
  - `dugong/dugong_app/persistence/event_journal.py`
  - `dugong/dugong_app/persistence/storage_json.py`
  - `dugong/dugong_app/persistence/sync_cursor_json.py`
  - `dugong/dugong_app/services/sync_engine.py`
  - `dugong/dugong_app/services/daily_summary.py`
  - `dugong/dugong_app/services/journal_compaction.py`
  - `dugong/dugong_app/debug.py`
  - `dugong/docs/schema_migrations.md`
  - `dugong/README.md`
  - `dugong/tests/test_event_journal_and_summary.py`
  - `dugong/tests/test_sync_engine.py`
  - `dugong/tests/test_transport_github.py`
  - `dugong/tests/test_transport_file.py`
  - `dugong/tests/test_storage_json_atomic.py`
  - `dugong/tests/test_controller_policy.py`
  - `dugong/tests/test_journal_compaction.py`
- Changes:
  - Centralized config via `DugongConfig`; unified data dir policy (`%APPDATA%/dugong` on Windows, `~/.dugong` on mac/linux, override by `DUGONG_DATA_DIR`).
  - Journal now has single-source dedupe by `event_id`, bad-line tolerant reader, optional `fsync` append.
  - State snapshot write upgraded to atomic `tmp + fsync + os.replace`.
  - Protocol decode compatibility clarified (`v1/v1.1/v1.2`) with migration doc.
  - Sync engine upgraded with status classification (`auth_fail/rate_limited/offline/retrying`), exponential backoff, and incremental cursor-based sync.
  - Added persistent sync cursor file `sync_cursor.json`.
  - Added adaptive auto-sync policy (idle backoff multiplier) and smarter remote signal prioritization in controller.
  - Added debug CLI commands:
    - `last-events`
    - `summary`
    - `compact-journal` (roll up old daily files into one `daily_rollup` event per day).
  - Added safe journal compaction that preserves day-level summary while shrinking old data.
- Validation:
  - `python -m pytest -q` -> 25 passed
  - `python -m dugong_app.debug compact-journal --keep-days 7 --dry-run` -> executable

## 2026-02-18 18:48:00
- Scope: P0/P1 hardening (compaction idempotence + paused auth state + observability).
- Files:
  - `dugong/dugong_app/services/journal_compaction.py`
  - `dugong/dugong_app/services/sync_engine.py`
  - `dugong/dugong_app/persistence/sync_cursor_json.py`
  - `dugong/dugong_app/persistence/event_journal.py`
  - `dugong/dugong_app/interaction/transport_github.py`
  - `dugong/dugong_app/debug.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/README.md`
  - `dugong/tests/test_journal_compaction.py`
  - `dugong/tests/test_sync_engine.py`
  - `dugong/tests/test_sync_cursor_storage.py`
- Changes:
  - Compaction metadata hardened: `compaction_version`, `rolled_up_from_dates`, `rolled_up_source` and idempotent skip logic.
  - Sync cursor upgraded to structured state:
    - `file_cursors`
    - `last_seen_event_id_by_source`
    - backward-compatible load for old flat cursor format.
  - Sync engine adds paused auth state:
    - `auth_fail/auth_missing` => `paused` on auto sync until manual `force` sync.
  - Added rollup-vs-raw protection in sync engine:
    - skip remote `daily_rollup` if local already has raw events for same `(date, source)`.
  - EventJournal now tracks `bad_lines_skipped` per read; CLI summary prints it.
  - Debug CLI adds `config` command with masked token output.
  - GitHub transport error formatting includes rate-limit reset hint when status=429.
- Validation:
  - `python -m pytest -q` -> 27 passed
  - `python -m dugong_app.debug config` -> OK (token masked)
  - `python -m dugong_app.debug summary --today` -> includes `bad_lines_skipped`

## 2026-02-18 19:08:00
- Scope: Backend v0.1 hardening follow-up (chain regression + health + migration guardrails).
- Files:
  - `dugong/dugong_app/services/sync_engine.py`
  - `dugong/dugong_app/persistence/sync_cursor_json.py`
  - `dugong/dugong_app/persistence/runtime_health_json.py`
  - `dugong/dugong_app/persistence/event_journal.py`
  - `dugong/dugong_app/controller.py`
  - `dugong/dugong_app/services/journal_compaction.py`
  - `dugong/dugong_app/services/data_migration.py`
  - `dugong/dugong_app/debug.py`
  - `dugong/README.md`
  - `.gitignore`
  - `dugong/tests/test_sync_compaction_chain.py`
  - `dugong/tests/test_sync_cursor_storage.py`
  - `dugong/tests/test_debug_cli.py`
  - `dugong/tests/test_journal_compaction.py`
  - `dugong/tests/test_sync_engine.py`
- Changes:
  - Added combo regression coverage for `cursor × compaction × sync`:
    - compacted rollup sync import idempotence
    - local raw + remote rollup skip correctness
    - restart continues incremental from legacy cursor file.
  - Sync cursor schema expanded with `last_seen_timestamp_by_source` (diagnostic watermark).
  - Added persistent backend health snapshot `sync_health.json`.
  - Added `debug health` command with:
    - sync state / paused reason
    - unread remote count
    - bad lines skipped
    - per-source latest event/timestamp
    - last push/pull timestamp and counts.
  - Auth failures now enter `paused` flow for auto sync (manual force sync still allowed).
  - Startup adds non-destructive legacy repo-data migration into unified data dir.
  - Strengthened `.gitignore` to avoid accidental runtime/token artifact commits.
- Validation:
  - `python -m pytest -q` -> 31 passed
  - `python -m dugong_app.debug health` -> OK
  - `python -m dugong_app.debug config` -> OK

## 2026-02-18 19:26:00
- Scope: Stability harness + UI background final rollback alignment.
- Files:
  - `dugong/scripts/stress_sync.py`
  - `dugong/README.md`
  - `dugong/dugong_app/ui/shell_qt.py`
- Changes:
  - Added stability harness script:
    - periodic fake events (`manual_ping`/`mode_change`)
    - forced sync interval
    - random network errors
    - simulated auth fail (401) / rate limit (429)
    - schema mismatch injection
    - compaction cycle + crash-skip simulation
  - Added real-time terminal progress bar for long runs (percent/elapsed/sync_fail/paused/sent).
  - Updated README with stress harness commands (`--hours 24/72` and smoke run).
  - Restored UI to agreed visual baseline:
    - full-width shell
    - tiled scrolling background mode (accepted current behavior)
    - `quit` button + `Esc` exit retained.
- Validation:
  - `python scripts/stress_sync.py --clean --hours 0.005` -> OK
  - `python scripts/stress_sync.py --clean --hours 0.002` -> OK (progress bar shown)
  - `python -m pytest -q tests\\test_entrypoint.py` -> 1 passed

## 2026-02-18 11:09:07
- Scope: UI asset integration upgrade (Anson asset pack + runtime left mirror).
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/ui/assets/README.md
- Changes:
  - Auto-load and use animation groups: Swim_loop / Idle_loop / Turn / React_happy/chill/dumb.
  - Added runtime left-facing mirror generation from right-facing PNG frames.
  - Added free-move state machine: swim, idle, turn, react with boundary turn-around.
  - Mode/sprite/bubble now map to react frames so all provided UI assets are used.
  - Kept DugongShell interface contract unchanged.
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py -> ok
  - (cd dugong) python -m pytest -> 31 passed

## 2026-02-18 11:16:58
- Scope: roaming behavior upgrade + react_shock integration.
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/ui/assets/README.md
- Changes:
  - Replaced horizontal-only move with 2D random roaming (random targets across X/Y area).
  - Added direction-aware steering and boundary-safe target reselection.
  - Added React_shock loading (React_shock*) with fallback to existing reacts.
  - Added shock/chill irregular auto-trigger and bubble keyword trigger (ail/offline/auth/error/...).
  - Kept existing DugongShell API unchanged.
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py -> ok
  - (cd dugong) python -m pytest -> 31 passed

## 2026-02-19 07:46:25
- Scope: Shared aquarium MVP (multi-source Dugong rendering).
- Files:
  - dugong/dugong_app/controller.py
  - dugong/dugong_app/ui/shell_qt.py
- Changes:
  - Controller now aggregates remote source presence from synced events (source/mode/last_seen).
  - Refresh pipeline now passes shared entity list to UI (local + remote sources).
  - UI now renders multiple independent Dugongs in the same aquarium (one per source).
  - Each source has independent movement path and name label; local and remote both roam.
  - Kept backward compatibility by preserving existing DugongShell API behavior.
- Validation:
  - python -m py_compile dugong/dugong_app/controller.py dugong/dugong_app/ui/shell_qt.py -> ok
  - (cd dugong) python -m pytest -> 31 passed

## 2026-02-19 08:23:05
- Scope: skin folder system by skin_id (remove hardcoded asset path coupling).
- Files:
  - dugong/dugong_app/config.py
  - dugong/dugong_app/controller.py
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/ui/assets/README.md
- Changes:
  - Added config field skin_id from env DUGONG_SKIN_ID (default: default).
  - DugongShell now receives skin_id and loads assets by folder id.
  - Loader priority: assets/<skin_id>/ -> assets/default/ -> legacy assets/ flat root.
  - Created ssets/default/ and copied current PNG set as initial default skin.
  - Kept filename-based action mapping (same filenames across skins, no new hardcode).
- Validation:
  - python -m py_compile dugong/dugong_app/config.py dugong/dugong_app/controller.py dugong/dugong_app/ui/shell_qt.py -> ok
  - (cd dugong) python -m pytest -> 31 passed

## 2026-02-19 08:27:38
- Scope: adjust skin root to assets/dugong_skin/<skin_id> and verify horse skin folder.
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/ui/assets/README.md
- Changes:
  - Skin loader root changed to ssets/dugong_skin/.
  - Priority updated: dugong_skin/<id> -> dugong_skin/default -> assets/default -> assets/.
  - Verified dugong_skin/horse folder resolves correctly.
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py dugong/dugong_app/config.py dugong/dugong_app/controller.py -> ok
  - (cd dugong) python -m pytest -> 31 passed

## 2026-02-19 10:11:48
- Scope: Pomodoro V1 + reward system (manual-start anti-AFK) integrated end-to-end.
- Files:
  - dugong/dugong_app/services/pomodoro_service.py
  - dugong/dugong_app/services/reward_service.py
  - dugong/dugong_app/persistence/pomodoro_state_json.py
  - dugong/dugong_app/persistence/reward_state_json.py
  - dugong/dugong_app/core/events.py
  - dugong/dugong_app/controller.py
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/config.py
  - dugong/dugong_app/debug.py
  - dugong/tests/test_pomodoro_reward.py
  - dugong/README.md
- Changes:
  - Added Pomodoro state machine service: IDLE/FOCUS/BREAK/PAUSED.
  - Enforced manual-only start for focus (no auto start on idle/restart).
  - Implemented phase flow: FOCUS auto->BREAK, BREAK complete -> IDLE (manual next start).
  - Added monotonic-time countdown model with paused restore behavior on restart.
  - Added Pomodoro events: pomo_start/pause/resume/skip/complete.
  - Added reward service with idempotent grant by session_id and validity ratio gate.
  - Added reward_grant event and local pearl accumulation.
  - Added persistent files: pomodoro_state.json and reward_state.json.
  - Controller now wires Pomodoro tick/actions, sync signaling, reward grant emission.
  - UI added minimal Pomodoro controls: pomo / pause / skip + status text line.
  - README updated with Pomodoro env vars and V1 behavior rules.
- Validation:
  - python -m py_compile dugong/dugong_app/controller.py dugong/dugong_app/ui/shell_qt.py dugong/dugong_app/services/pomodoro_service.py dugong/dugong_app/services/reward_service.py -> ok
  - (cd dugong) python -m pytest -q -> 34 passed

## 2026-02-19 10:20:42
- Scope: Pomodoro V1 test hardening and debug guardrails.
- Files:
  - dugong/dugong_app/debug.py
  - dugong/tests/test_pomodoro_reward.py
  - dugong/tests/test_debug_cli.py
  - dugong/README.md
- Changes:
  - Added python -m dugong_app.debug pomo command to inspect pomodoro/reward runtime snapshot.
  - Added contract test: manual start only (IDLE -> FOCUS), no start while running/paused.
  - Added sleep-like time jump test (monotonic time correctness under delayed tick).
  - Added reward threshold boundary test (exact ratio grants).
  - Added debug CLI test for pomo output schema.
- Validation:
  - python -m py_compile dugong/dugong_app/debug.py dugong/tests/test_pomodoro_reward.py dugong/tests/test_debug_cli.py -> ok
  - (cd dugong) python -m pytest -q -> 38 passed

## 2026-02-19 10:27:49
- Scope: Added stress_pomo.py black-box harness + CI smoke gate.
- Files:
  - dugong/scripts/stress_pomo.py
  - dugong/tests/test_stress_pomo.py
  - dugong/README.md
- Changes:
  - New Pomodoro stress harness with ast and soak modes.
  - Supports action driving without UI: start/pause/resume/skip + tick/time-jump + restart simulation.
  - Adds replay jitter simulation for duplicate completion delivery.
  - Outputs PASS/FAIL with quality gates and writes JSON log to <workdir>/logs/stress_pomo_*.json.
  - Metrics include: completed total, effective rate, expected vs actual pearls delta, dedupe hits, invariant violations, recovery checks.
  - Added pytest smoke test to run a short fast-mode gate in CI (	est_stress_pomo_fast_smoke).
- Validation:
  - python -m py_compile dugong/scripts/stress_pomo.py dugong/tests/test_stress_pomo.py -> ok
  - (cd dugong) python -m pytest -q -> 39 passed

## 2026-02-19 10:37:10
- Scope: V2 5-minute demo helper script (fixed timeline + operator prompts).
- Files:
  - dugong/scripts/demo_v2.py
  - dugong/tests/test_demo_v2.py
  - dugong/README.md
- Changes:
  - Added demo_v2.py to print deterministic 5-minute A/B demo timeline.
  - Added A/B env command blocks (GitHub or file transport) for quick setup.
  - Added optional --run countdown mode for live demo operation.
  - Added optional co-focus segment in timeline via --include-cofocus.
  - Added smoke unit test for timeline end marker.
- Validation:
  - python -m py_compile dugong/scripts/demo_v2.py dugong/tests/test_demo_v2.py -> ok
  - (cd dugong) python -m pytest -q -> 40 passed

## 2026-02-19 10:48:53
- Scope: co-focus milestone system (overlap focus tracking + milestone bonus).
- Files:
  - dugong/dugong_app/controller.py
  - dugong/dugong_app/core/events.py
  - dugong/dugong_app/services/reward_service.py
  - dugong/dugong_app/config.py
  - dugong/dugong_app/debug.py
  - dugong/tests/test_pomodoro_reward.py
  - dugong/tests/test_debug_cli.py
  - dugong/README.md
- Changes:
  - Added co_focus_milestone event and remote reflection bubble/priority handling.
  - Controller now tracks local+remote focus overlap seconds and emits milestone events when threshold reached.
  - Added configurable co-focus params:
    - DUGONG_COFOCUS_MILESTONE_SECONDS (default 600)
    - DUGONG_COFOCUS_BONUS_PEARLS (default 5)
  - Reward service now supports idempotent co-focus milestone grants (granted_cofocus_milestones).
  - Reward snapshot extended with cofocus_seconds_total and milestone grant history.
  - debug pomo now outputs co-focus counters.
  - State text now includes co-focus minutes (C:<m>m).
- Validation:
  - (cd dugong) python -m pytest -q -> 42 passed

## 2026-02-19 10:51:17
- Scope: Added debug pomo --watch realtime monitor.
- Files:
  - dugong/dugong_app/debug.py
  - dugong/tests/test_debug_cli.py
  - dugong/README.md
- Changes:
  - python -m dugong_app.debug pomo now supports:
    - --watch (stream snapshots)
    - --interval (refresh interval, seconds)
    - --iterations (loop limit; 0=infinite, used in tests)
  - Added automated test for watch mode output stability.
  - README debug command examples updated.
- Validation:
  - python -m py_compile dugong/dugong_app/debug.py dugong/tests/test_debug_cli.py -> ok
  - (cd dugong) python -m pytest -q -> 43 passed

## 2026-02-19 10:53:16
- Scope: UI polish pass (minimal, no logic change): compact controls + pomodoro corner chip + unified completion feedback style.
- Files:
  - dugong/dugong_app/ui/shell_qt.py
- Changes:
  - Added top-right Pomodoro status chip with state color coding (FOCUS/BREAK/PAUSED/IDLE).
  - Reduced control bar visual weight: lower height, compact button sizing/typography.
  - Kept hover-to-show interaction and existing callbacks unchanged.
  - Unified completion-like bubble feedback style: complete/pearls/milestone messages stay longer and trigger short celebration react.
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py -> ok
  - (cd dugong) python -m pytest -q -> 43 passed

## 2026-02-19 10:56:29
- Scope: Pomodoro control UX adjustment: Start/Pause/Resume now uses a single toggle button.
- Files:
  - dugong/dugong_app/ui/shell_qt.py
- Changes:
  - Replaced separate pomo + pause buttons with one dynamic toggle button.
  - Button label/state mapping:
    - IDLE -> start
    - FOCUS/BREAK -> pause
    - PAUSED -> esume
  - Toggle keeps existing callbacks and logic (start or pause/resume) unchanged.
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py -> ok
  - (cd dugong) python -m pytest -q -> 43 passed

## 2026-02-19 11:10:45
- Scope: UI reward feedback upgrade (pearl counter + floating reward text).
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/controller.py
- Changes:
  - Added top-left Pearls counter chip: total pearls + focus/day streak.
  - Added floating +N pearls text animation above local Dugong when pearls increase.
  - Extended UI update contract with optional eward_stats payload (controller now passes it).
  - Preserved core logic/event flow (display-only enhancement).
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py dugong/dugong_app/controller.py -> ok
  - (cd dugong) python -m pytest -q -> 43 passed

## 2026-02-19 19:12:06
- Scope: Game-style hover attribute card (replace EMF-first feel with visible creature profile).
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/controller.py
- Changes:
  - Added mouse-hover card for local and remote Dugongs.
  - Local card now shows stage/title, mode/pomodoro, mood-energy-focus, pearls/streak/day.
  - Peer card shows ally profile (mode/pomodoro/last seen) for co-focus readability.
  - Added stage mapping by pearl count (E..S rank + title).
  - Shared entities now include pomo_phase so remote hover card can reflect focus/break state.
  - Stored raw state text for local stat parsing and enabled hover repaint updates.
- Validation:
  - python -m py_compile dugong/dugong_app/ui/shell_qt.py dugong/dugong_app/controller.py -> ok
  - (cd dugong) python -m pytest -q -> 43 passed

## 2026-02-19 19:21:10
- Scope: Product-layer completion pass (not only hover card): stronger rewards + pearl assetization + MVP shop + life-like stat persistence hooks.
- Files:
  - dugong/dugong_app/services/reward_service.py
  - dugong/dugong_app/controller.py
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/debug.py
  - dugong/tests/test_pomodoro_reward.py
  - dugong/README.md
- Changes:
  - Reward system upgraded:
    - Added 	oday_pearls and lifetime_pearls.
    - Replaced linear streak bonus with tiered rewards (1-3, 4-6, 7+).
  - Added mini-shop backend in reward service:
    - purchasable/equippable skin/bubble/title (idempotent equip path for owned items).
  - Added mood persistence nudges tied to behavior:
    - focus complete +5, skip -3, co-focus milestone +2, idle tick decay -1.
  - Controller/UI integration:
    - state line simplified (de-emphasize old EMF display in main line).
    - reward payload now includes current/today/lifetime + equipped cosmetic ids.
    - local profile payload passed to UI hover card (no longer regex-dependent).
    - shop action callback wired in controller.
  - UI gameplay feel:
    - shop button with 3-item MVP menu.
    - title prefix in local name tag.
    - bubble style swaps with equipped bubble style.
    - runtime local skin swap when equipped skin changes.
    - pearl counter now shows today/lifetime context.
  - Debug output extended with new reward/cosmetic fields.
- Validation:
  - python -m py_compile dugong/dugong_app/services/reward_service.py dugong/dugong_app/controller.py dugong/dugong_app/ui/shell_qt.py dugong/dugong_app/debug.py dugong/tests/test_pomodoro_reward.py -> ok
  - (cd dugong) python -m pytest -q -> 45 passed

## 2026-02-19 19:41:30
- Scope: Full product-layer sync follow-up: sync pearl/title cosmetics across peers + complete prior roadmap parts.
- Files:
  - dugong/dugong_app/core/events.py
  - dugong/dugong_app/services/reward_service.py
  - dugong/dugong_app/controller.py
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/debug.py
  - dugong/tests/test_pomodoro_reward.py
  - dugong/tests/test_controller_policy.py
  - dugong/README.md
- Changes:
  - Added profile_update event and propagation path for cross-machine profile sync.
  - Remote Dugong cards now show synced pearls/today/streak/title (not only mode/pomo).
  - Remote name tags now include synced title prefix.
  - Reward model expanded with 	oday_pearls + lifetime_pearls and tiered streak rewards.
  - Added MVP shop backend + UI hook (skin/bubble/title purchase/equip).
  - Local mood persistence nudges tied to behavior outcomes (complete/skip/co-focus/idle).
  - Local profile now passed structurally to UI hover card (no regex dependency).
  - README updated with profile sync event.
- Validation:
  - python -m py_compile dugong/dugong_app/controller.py dugong/dugong_app/ui/shell_qt.py dugong/dugong_app/services/reward_service.py dugong/dugong_app/core/events.py dugong/tests/test_controller_policy.py -> ok
  - (cd dugong) python -m pytest -q -> 46 passed
