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
