# Anson Update Log

## Template
- Time: YYYY-MM-DD HH:MM:SS
- Scope:
- Files:
  - path/to/file
- Changes:
  - ...
- Validation:
  - command -> result

## 2026-02-17 04:26:00
- Scope: UI implementation TODO from Cornelius handoff.
- Please Implement:
  - Keep changes inside `dugong/dugong_app/ui/*` when possible.
  - Add sprite/assets rendering (not title-text only).
  - Improve bubble expression by `mode` + stat ranges.
  - Keep cross-platform context menu support (`Button-2/3`, `Control-Button-1`).
- Contract to Keep:
  - `DugongShell(on_mode_change, on_click)`
  - `update_view(sprite, state_text, bubble)`
  - `Renderer.sprite_for(state)`
  - `Renderer.bubble_for_click(state)`
- Done Criteria:
  - `python -m pytest` passes.
  - `python -m dugong_app.main` shows visible sprite changes by state.
## 2026-02-17 04:45:00
- Scope: UI V1 可爱陪伴风格（Emoji 皮肤占位）+ Hover Action Bar（替代 macOS 右键主入口），不触碰 core/controller/interaction。
- Files:
  - dugong/dugong_app/ui/renderer.py
  - dugong/dugong_app/ui/shell_qt.py
- Changes:
  - Renderer:
    - `sprite_for(state)` 由返回字符串 key（sleepy/focused/happy/neutral）调整为返回 Emoji token（🦭 / 💤🦭 / 🤓🦭 / ✨🦭），用于 V1 占位皮肤。
    - `bubble_for_click(state)` 文案调整为“可爱陪伴型”短句风格（按 mode 分流）。
  - Shell (Tkinter):
    - 新增大号 `pet_label` 用于显示 Dugong 外貌（Emoji），`update_view()` 中用 `sprite` 更新该标签。
    - 引入 Hover Action Bar（study/chill/rest）作为主交互入口：鼠标移入显示，移出/拖动隐藏；右键菜单保留为备用入口（Win 友好、mac 兼容）。
    - 保持接口契约不变：`DugongShell.update_view(...) / schedule_every(...) / run()` 与回调 `on_mode_change/on_click` 不变。
- Validation:
  - `python -m pytest` -> (待 Anson 本机补填结果)
  - `python -m dugong_app.main` -> (待 Anson 本机补填结果：能启动/能切 mode/能 click bubble)
- Blocked / Not Implemented:
  - Emoji 仅为占位：尚未接入 `ui/assets/` 的真实 sprite（PNG/GIF）加载与切换。
  - 暂无动画（无帧切换/无状态过渡动效）。
  - Hover Action Bar 在不同 Tk 版本上可能存在轻微闪烁/敏感问题（如出现，需进一步 debounce 调整）。
- Notes for Cornelius:
  - UI 未触碰 core/controller；若后续要做“mood 独立于 mode”的交互，需要先在 core/controller 定义新回调/协议，再由 UI 侧接入。
## 2026-02-17 05:20:00
- Scope: UI 透明底跨平台实现（mac 真透明 / win 色键透明 / 自动降级），修复 BG 未生效导致的不透明问题。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
- Changes:
  - 新增 apply_transparency()，按平台选择透明方案并返回 BG
  - 将 frame/title/pet/state/bubble 的 bg 统一为 BG（透明的关键）
  - frame 去边框（bd=0, relief=FLAT），减少透明边缘残留
  - 增加调试输出：platform + transparency mode
- Validation:
  - [ ] python -m dugong_app.main
  - [ ] 观察打印 transparency mode 是否为 mac/win（非 fallback）
- Not Implemented / Notes:
  - 若 transparency mode 为 fallback，表示当前 Tk 环境不支持 cutout transparency，只能 alpha 降级或后续迁移 Qt。

## 2026-02-17 06:05:00
- Scope: minimal UI follow-up for new focus sessions.
- Core output added:
  - `focus_sessions.json` (derived from mode changes)
- Suggested minimal UI task (optional):
  - Read `focus_sessions.json` and display a tiny text hint like `sessions today: N`.
- Constraints:
  - Do not change existing UI constructor/update_view signatures.
  - Keep all current interactions unchanged.

## 2026-02-17 06:40:00
- Scope: V2 M1 UI minimal follow-up (no mandatory UI refactor).
- Core already provides:
  - remote unread count in state text (`R:<n>`)
  - sync status in state text (`S:ok/fail/disabled`)
  - remote bubble reflection for `manual_ping` and `mode_change`
- Optional minimal UI for Anson (keep existing structure):
  - Parse state_text and style `R:` as badge-like highlight.
  - Parse `S:` and map to tiny dot color (green/yellow/red).
  - Keep all existing callbacks/signatures unchanged.

## 2026-02-17 07:05:00
- Scope: V2 github transport landed (UI no change required).
- Core delivered:
  - `DUGONG_TRANSPORT=github` route available.
  - Remote reflection still via current bubble + `R:/S:` state text.
- Optional UI next step (minimal):
  - make `S:ok/fail/disabled` more visible as color dot; no API change needed.

## 2026-02-17 07:18:00
- Scope: quick sync UX added.
- UI changes already landed:
  - new `sync` button in action bar
  - new `sync now` in context menu
- No further UI change required for this step.

## 2026-02-17 08:10:00
- Scope: 3-frame seal animation hook added.
- Required assets:
  - `dugong/dugong_app/ui/assets/seal_1.png`
  - `dugong/dugong_app/ui/assets/seal_2.png`
  - `dugong/dugong_app/ui/assets/seal_3.png`
- Behavior:
  - Auto-loop if files exist.
  - Fallback to emoji if files are missing.

## 2026-02-18 17:15:11
- Scope: Anson UI 总更新汇总（基于当前 PySide6 版本 `shell_qt.py`）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/ui/assets/bg_ocean.png
  - dugong/dugong_app/ui/assets/seal_1.png
  - dugong/dugong_app/ui/assets/seal_2.png
  - dugong/dugong_app/ui/assets/seal_3.png
- Total Updates:
  - UI 框架从 Tk 方案切换为 PySide6 `QWidget` 壳层，保留 `DugongShell` 既有接口签名不变。
  - 窗口行为升级为无边框、置顶、工具窗，并开启 `WA_TranslucentBackground` 透明背景。
  - 主视觉改为 `paintEvent` 自绘：
    - 海底背景 `bg_ocean.png` 横向循环滚动。
    - Dugong 三帧 `seal_1/2/3` 按 `1-2-3-2` 序列循环动画。
  - 新增缩放缓存逻辑：窗口尺寸变化时重建背景与角色缩放图，保证跨分辨率显示稳定。
  - 新增双计时器机制：
    - 角色动画帧计时器（默认 320ms）
    - 背景滚动计时器（默认 16ms）
  - 覆盖层 UI 完整化：
    - 标题与状态文案
    - 气泡组件（自动隐藏）
    - Hover Action Bar（`study/chill/rest/ping/sync`）
  - 交互增强：
    - 鼠标拖拽移动窗口
    - 左键释放触发 `on_click`
    - 按钮分别回调 `on_mode_change` / `on_manual_ping("checkin")` / `on_sync_now`
  - 资源加载改为严格校验：背景图或任一 Dugong 帧缺失会直接抛错，避免静默降级。
  - `schedule_every` 使用 Qt `QTimer` 托管，并将 timer 引用保存在窗口实例中，防止被回收。
- Contract Kept:
  - `DugongShell(on_mode_change, on_click, on_manual_ping=None, on_sync_now=None)`
  - `DugongShell.update_view(sprite, state_text, bubble)`
  - `DugongShell.schedule_every(seconds, callback)`
  - `DugongShell.run()`
- Notes:
  - 当前 `update_view(sprite, ...)` 已不再使用 `sprite` 参数驱动渲染，角色显示由本地帧动画主导。
