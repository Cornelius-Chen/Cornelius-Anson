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
