# Copilot instructions for Mina-a-Assistente-Virtual-Do-G.E.R.A

## Build, run, and lint commands

- Install dependencies: `pip install -r requirements.txt`
- Install macOS dependencies: `pip install -r requirements_mac.txt`
- Run the GUI launcher: `python main_gui.py`
- Run fullscreen: `python main_gui.py -f`
- Run studio/layout-editor mode: `python main_gui.py -s`
- Lint with Flake8: `flake8 .`
- Format with Black: `black .`
- Sort imports with isort: `isort .`
- Build the optional native STT helper on Linux-like systems: `gcc -shared -fPIC stt.c -o libs/stt/libstt.so -lportaudio -lcurl`

There is no configured automated test suite in this repo right now: no `tests/`, `pytest.ini`, or other test runner setup was found. The only test-like utility in the tree is `python vadtest.py`.

## High-level architecture

- `main_gui.py` is the real entrypoint. It starts `QApplication`, wraps it in `qasync.QEventLoop`, configures logging, parses `-f/--fullscreen` and `-s/--studio`, then wires together `GuiDisplay`, `ChatBridge`, and the optional `STTController`.
- The display stack is split between Python and QML:
  - `src/display/gui_display.py` owns the Qt window and exposes async update methods used by the rest of the app.
  - `src/display/gui_display_model.py` is the Python-to-QML data model for status text, current emotion, reply text, and button state.
  - `src/display/layout_config_model.py` loads and persists `config/layout_config.json`, so layout/theme changes belong there instead of hard-coded QML constants.
- `src/utils/chat_bridge.py` is the bridge to the native `apicomm` executable in the repository root. It streams backend output line-by-line and treats protocol markers as control messages:
  - `EMOTION:<name>`
  - `PAUSE:<ms>`
  - `CHUNK|<delay>|<emotion>|<text>`
  - `<<END>>`
  Preserve that wire format if you touch the Python/C boundary.
- `src/utils/stt_client.py` is a `ctypes` wrapper around the compiled STT shared library under `libs/stt/`. `main_gui.py` deliberately degrades gracefully if the STT library cannot be loaded, so talk-button failures should not take down the GUI.
- `src/views/` contains secondary windows and widgets, especially activation and settings flows. Shared Qt window/task behavior lives in `src/views/base/`.
- `src/utils/config_manager.py` and `src/utils/resource_finder.py` are core infrastructure:
  - `ConfigManager.get_instance()` owns config loading, merging defaults, and dot-path reads such as `get_config("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL")`.
  - `resource_finder` resolves project assets, models, config, and libs across local runs and packaged/frozen builds; prefer it over hard-coded relative paths.
- Non-Python assets matter to runtime behavior:
  - `config/config.json` stores runtime settings.
  - `config/layout_config.json` drives theme/layout values used by QML.
  - `assets/` contains emotion/media resources selected by `GuiDisplay`.
  - `libs/` contains native dependencies (`stt`, `libopus`, `webrtc_apm`).

## Key repository conventions

- This codebase is async-first even in the GUI layer. New UI-facing flows should fit the existing `async`/`await` style and use `asyncio.to_thread(...)` for blocking native or I/O work instead of blocking the Qt event loop.
- Keep GUI state changes flowing through the display abstractions (`GuiDisplay`, `GuiDisplayModel`, `LayoutConfigModel`) instead of mutating QML-facing state ad hoc.
- Use `ConfigManager.get_instance()` for settings access and updates; configuration keys are organized as nested JSON with dot-path lookups, and defaults are defined in `ConfigManager.DEFAULT_CONFIG`.
- Use `get_logger(__name__)` from `src/utils/logging_config.py` instead of creating ad hoc loggers. `setup_logging()` writes both colored console logs and rotating files in `logs/app.log`.
- When working with assets, models, config files, or bundled libraries, use `resource_finder` helpers rather than assuming the current working directory. The repo supports both source runs and packaged layouts.
- Emotion/display updates expect lower-case emotion names that map to asset files when possible; `GuiDisplay` falls back across multiple image extensions and can leave non-file values (for example emoji text) untouched.
- Studio mode is a real editing path for the UI layout. If you change QML sizing/theming behavior, check whether the change belongs in `config/layout_config.json` and `LayoutConfigModel` instead of only in `gui_display.qml`.
- The README contains some inherited content from the upstream full `py-xiaozhi` project. For implementation decisions in this fork, trust the actual files in this repo first—especially `main_gui.py`, `src/display/`, `src/utils/`, and the current config/native-library layout.
