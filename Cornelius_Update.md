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
