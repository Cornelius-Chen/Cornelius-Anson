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

## 2026-02-20 22:00:36
- Scope: Shop 皮肤位微调到左侧木架 + 徽章最小可见 UI 补齐。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 皮肤区保持第一版透明点击风格（无大卡片遮挡），仅调整三张皮肤坐标到左侧三层木架上。
  - 新增 `skin_rects` 三组锚点，按背景图木架位置做精细定位。
  - 徽章区保留原点击图标位，同时新增 `badge_tag`（名称 + 状态/价格）可视标签，解决“徽章没有对应 UI”问题。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:05:29
- Scope: Shop 皮肤位终版微调（按要求去掉 default、horse 在 king 左侧、整体缩小约 50%）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 皮肤上架项从 3 个改为 2 个：仅保留 `horse`、`king`（移除 `default`）。
  - 皮肤坐标改为同一层并排：`horse` 在 `king` 正左侧。
  - 皮肤点击区域和图标尺寸缩小到上一版约 50%。
  - 徽章区图标与标签尺寸同步缩小约 50%，并微调位置，保持整体比例一致。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:08:10
- Scope: Shop 整体等比例缩小（背景 + 皮肤 + 徽章一起 0.5），避免只缩局部元素。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 在 `_open_shop_dialog()` 增加统一缩放系数 `shop_scale = 0.5`，对 shop 背景尺寸（`target_h/max_w`）整体生效。
  - 保留 `horse/king` 同层并排（horse 在 king 左侧），并恢复皮肤/徽章元素到与背景同尺度的相对比例，避免“二次缩小”。
  - 徽章标签尺寸与样式恢复为常规比例，以匹配缩小后的整体 shop 画面。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:10:04
- Scope: Shop 皮肤位最终微调（king 在 horse 左侧，king/horse UI 放大 2 倍）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 皮肤顺序改为 `king`（左）→ `horse`（右）。
  - 两个皮肤点击/显示矩形统一放大到当前版本的 2 倍。
  - 其余 shop 缩放与徽章布局保持不变。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:11:55
- Scope: Shop 皮肤位微调（horse 移到 king 正上方架子）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 保持 king 位置不变。
  - horse 改为与 king 同一 x 轴，y 上移到上一层架子位置。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:16:22
- Scope: Dugong Shop 左上角新增放大/缩小按钮（整体缩放）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 新增 `self._shop_scale`（默认 `0.5`）作为 shop 统一缩放系数。
  - `_open_shop_dialog()` 使用 `self._shop_scale` 控制背景尺寸，所有元素随背景一起缩放。
  - 在 shop 左上角新增 `-` / `+` 按钮：
    - `-` 每次缩小 `0.1`
    - `+` 每次放大 `0.1`
    - 缩放范围限制为 `0.35 ~ 1.20`
  - 点击缩放按钮后自动关闭并重开 shop，应用新比例。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:19:48
- Scope: Dugong Shop 增加“长按边缘拖动”交互。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 新增 shop 拖动状态机：按住 shop 边缘约 `220ms` 后进入拖动模式。
  - 仅边缘触发拖动（中间内容区不触发），避免影响商品点击。
  - 拖动后记录手动位置 `self._shop_manual_pos`，主窗口移动时不再强制吸回中心。
  - 拖动位置带屏幕边界钳制，防止商店窗口拖出可视区域。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:37:08
- Scope: 用 assets 里的徽章 UI 替换 shop 中 Explorer/Wanderer 按钮占位图。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - `_shop_badge_preview()` 现在优先从 `dugong/dugong_app/ui/assets/badge/` 加载徽章图片。
  - 支持大小写文件名匹配（如 `Explorer.PNG`、`wanderer.PNG`）。
  - 若资源缺失，才回退到原有圆形字母占位图。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:39:02
- Scope: 修复 shop 中 Wanderer 徽章图未加载问题。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - `_shop_badge_preview()` 增加别名映射：`drifter -> wanderer`。
  - 现在 `title_id=drifter` 的商店项会正确命中 `assets/badge/wanderer.PNG`。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:40:56
- Scope: 去掉 shop 两个徽章 UI 下方文字栏。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 删除徽章项下方 `badge_tag` 标签绘制，仅保留徽章图片和点击逻辑。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:56:20
- Scope: 模式点击音效 + 功能栏静音开关。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 新增模式音效映射（`assets/sound`）：
    - `study` -> `skeleton.mp3`
    - `chill` -> `pvz.mp3`
    - `rest` -> `mc.mp3`
  - `_emit_mode()` 触发时增加 `_play_mode_sound(mode)`。
  - `S` 页功能栏新增 `mute` 按钮（`mute: off/on`），可切换静音。
  - 静音状态会同步到所有模式音频输出。
  - 若 `QtMultimedia` 不可用，自动静默降级（不影响 UI 其他功能）。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 22:58:55
- Scope: 修复模式按钮点击无声音问题（QtMultimedia 缺失环境兜底）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 根因：当前运行环境无 `PySide6.QtMultimedia`，原音频播放路径被静默跳过。
  - 新增 `self._mode_sound_files` 缓存音频路径，始终记录可用 mp3 文件。
  - `_play_mode_sound()` 优先走 QtMultimedia；不可用时自动走系统播放器兜底：
    - macOS: `afplay`
    - Windows: PowerShell `System.Windows.Media.MediaPlayer`
  - 仍保留 `mute` 开关，静音时不触发任何播放。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-20 23:02:01
- Scope: 修复字体别名告警 + mac 音频 `dta?/fmt?` 报错。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - Anson_Update.md
- Changes:
  - 去除所有硬编码字体族 `Segoe UI`，改为 `QtGui.QFont()` 系统默认字体并设置 size/weight，消除 `missing font family` 告警。
  - mac 音频兜底增强：对 `.mp3` 音频先生成临时 `.m4a` 播放路径（你的文件实际是 MP4 容器），再交给 `afplay`。
  - `afplay`/Windows PowerShell 播放进程改为 `stdout/stderr` 静默，避免终端刷错误文本。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`

## 2026-02-21 00:59:03
- Scope: 增加 Dugong 冷笑话库与随机播报（每 15-30 秒）。
- Files:
  - dugong/dugong_app/ui/shell_qt.py
  - dugong/dugong_app/ui/assets/jokes/cold_jokes.txt
  - dugong/dugong_app/ui/assets/README.md
  - Anson_Update.md
- Changes:
  - 新增笑话定时器（single-shot）：每次随机 15-30 秒后触发一次。
  - 触发时从笑话库随机抽取一句，通过现有 `show_bubble()` 显示。
  - 新增笑话库读取逻辑，默认读取：
    - `dugong/dugong_app/ui/assets/jokes/cold_jokes.txt`
    - 兼容回退：`dugong/dugong_app/ui/assets/cold_jokes.txt`
  - 笑话库规则：一行一条，空行与 `#` 注释行自动忽略。
  - 新增初始冷笑话样例，便于直接替换粘贴。
- Validation:
  - `cd dugong && python -m pytest -q` -> `46 passed`
