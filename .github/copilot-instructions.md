# Copilot instructions for Mina — Assistente Virtual do G.E.R.A

## Project overview
Mina is a **GUI-only fork of py-xiaozhi** with a PyQt5+QML interface, animated emotions, and a threaded STT/chat bridge. This repo ships **only the GUI display, settings dialogs, native helpers (`apicomm`, `libs/stt`, `libs/libopus`, `libs/webrtc_apm`) and configuration scaffolding**; no network backend, IoT, or MCP subsystem is bundled.

## Commands

### Prerequisites
- Install Python deps: `pip install -r requirements.txt`
- macOS helper deps: `pip install -r requirements_mac.txt`

### Run the GUI
- `python main_gui.py`
- `python main_gui.py -f` (fullscreen mode)
- `python main_gui.py -s` (studio/layout-editor mode)

### Diagnostics and testing
- `python vadtest.py` verifies the TTS/VAD helpers manually.
- `python -m compileall main_gui.py src` is the lightweight syntax check wired to `make check`/`make test`.
- There is no automated pytest-like suite; rely on manual runs or `make test`.

### Formatting and linting
- `python -m black .`
- `python -m isort .`
- `python -m flake8 .`

### Build helpers (see the Makefile)
- `make install-deps` (runs `apt-get update`/`apt-get install -y libcjson-dev libcurl4-openssl-dev` on Debian/Ubuntu).
- `make compile` (builds `apicomm` from `apicomm.c`).
- `make stt-linux` / `make stt-windows` recompile `stt.c` into the shared library your platform expects.
- `make check` / `make test` (calls `python -m compileall`).

## Environment variables
- `GROQ_API_KEY`: Required when the STT helper or chat bridge talks to Groq Whisper/AI.
- `CHAT_BACKEND`: `"groq"` for the Python Groq client or `"binary"` to run `./apicomm`.
- `STT_LIBRARY_PATH`: Points to `libs/stt/libstt.so` (or `stt.dll`) when the auto-discovery fails.

## High-level architecture

```
main_gui.py
├─ GuiDisplay (src/display/)
│  ├─ gui_display.qml           – QML layout + animations + emotion assets
│  ├─ GuiDisplayModel           – Python↔QML data bridge (status, emotion, text, buttons)
│  └─ LayoutConfigModel         – Exposes config/layout_config.json theme/layout fields
│
├─ ChatBridge (src/utils/chat_bridge.py)
│  ├─ Sends chat prompts to `apicomm` (binary mode) or Groq (Python mode)
│  ├─ Parses stdout markers (`EMOTION:`, `PAUSE:`, `CHUNK|delay|emotion|text`, `<<END>>`)
│  └─ Streams status/emotion updates to GuiDisplay
│
└─ STTClient (src/utils/stt_client.py)
   └─ ctypes wrapper around `libs/stt/{libstt.so,stt.dll}`; failures fall back gracefully and just disable the talk button.
```

### Runtime flow
1. Talk button → `STTController.toggle()` → native STT helper records audio.
2. `ChatBridge.send_and_stream()` streams chunks back (`CHUNK|delay|emotion|text`) and fires `on_emotion`, `on_control`, `on_chunk` handlers.
3. `GuiDisplay` updates the QML face via `GuiDisplayModel` and `LayoutConfigModel`.
4. Async helpers (`qasync`, `asyncio.to_thread`) keep the Qt event loop responsive.

## AI response format

The current `prompts.txt` prompt forces the model to respond with:

```
EMOTION: thinking
CHUNK|500|thinking|Hmm, deixa eu pensar...
CHUNK|300|confident|Sim, é exatamente isso!
PAUSE:150
CHUNK|250|laughing|Isso me lembra...
<<END>>
```

- `EMOTION:` drives the global emotion/face.
- Each `CHUNK|<delay>|<emotion>|<text>` tells the frontend how long to wait before showing the next word and which GIF to play.
- `PAUSE:<ms>` creates silent delays between chunks.
- Valid emotion names include `thinking, confident, happy, laughing, crying, surprised, neutral` etc.; `GuiDisplay` tries to resolve them inside `assets/emojis/<emotion>.gif` and falls back to emoji text when no file exists.

## Key conventions

- **Async-first GUI**: Most I/O is `async def`. Use `asyncio.to_thread(...)` when calling blocking native code (STT, `apicomm`).
- **ConfigManager + LayoutConfigModel**: All config access goes through `ConfigManager.get_instance().get_config("SECTION.KEY")`; layout/theme values persist in `config/layout_config.json`.
- **ResourceFinder**: Use `resource_finder` helpers for assets, models, configs, and libs. The codebase supports running from source, frozen apps, or installers.
- **Logging**: Use `get_logger(__name__)`, which configures colored console output and a rotating file in `logs/app.log`.
- **QML bindings**: Update UI through `GuiDisplayModel` (signals for `statusText`, `emotionPath`, `ttsText`, `buttonText`, `buttonBarVisible`); avoid mutating QML state directly.
- **Studio mode**: Acts as a live layout editor. If you adjust spacing/theme, update `config/layout_config.json` and `LayoutConfigModel` so the data bindings stay in sync.
- **Native helpers**: `Makefile` reuses the same compiler flags as existing scripts (`gcc -O2 -march=native -Wall -Wextra`). `libs/stt` is optional; missing libs are logged but not fatal.

## File quick reference

| Purpose | Path |
| --- | --- |
| App entry point | `main_gui.py` |
| QML interface | `src/display/gui_display.qml` |
| Python UI bridge | `src/display/gui_display_model.py` |
| Chat logic | `src/utils/chat_bridge.py` |
| STT wrapper | `src/utils/stt_client.py` |
| Configuration | `config/config.json`, `config/layout_config.json` |
| Layout editing | `src/display/layout_config_model.py` |
| Active prompt | `prompts.txt` |
| VAD smoke test | `vadtest.py` |
| Native apicomm | `apicomm.c` → `apicomm` |

### Notes
- README content reflects the upstream full project; rely on the files within this repo (`main_gui.py`, `src/`, `config/`, `libs/`) when deciding what to edit.
