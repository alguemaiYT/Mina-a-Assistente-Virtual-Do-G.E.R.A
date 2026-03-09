# Copilot Instructions for Mina — Assistente Virtual do G.E.R.A

## Project Overview

Mina is a **GUI-only fork of py-xiaozhi** — a PyQt5+QML virtual assistant with an emotion-driven animated face, speech-to-text input, and an AI chat backend. The interface is designed for Portuguese/Brazilian usage. Core design goal: text responses from the AI are segmented into CHUNKs with per-chunk emotion tags that sync with animated GIF facial expressions.

## Commands

```bash
# Run the application
python main_gui.py
python main_gui.py --fullscreen        # fullscreen mode
python main_gui.py --studio            # layout editor mode

# Install dependencies
pip install -r requirements.txt        # Windows/Linux
pip install -r requirements_mac.txt   # macOS

# Diagnostic tools
python vadtest.py                      # Verify VAD/Audio input

# Code formatting & linting
black .
isort .
flake8
```

There is no formal test suite. Validation is done via local runs.

**Required environment variables:**

```bash
export GROQ_API_KEY="..."        # Groq Whisper (STT) + chat API
export CHAT_BACKEND="groq"       # "groq" (Python) or "binary" (C apicomm)
```

**Recompile C shared libraries if modified:**

```bash
# Windows (requires gcc/mingw)
gcc -shared -fPIC stt.c -o libs/stt/stt.dll -lportaudio -lcurl
# Linux
gcc -shared -fPIC stt.c -o libs/stt/libstt.so -lportaudio -lcurl
```

## Architecture

```
main_gui.py
├─ GuiDisplay (src/display/)        — PyQt5 widget hosting QML frontend
│   ├─ gui_display.qml              — QML visual layout & animations
│   ├─ GuiDisplayModel              — Python↔QML data bridge (emotion, text, status)
│   └─ LayoutConfigModel            — Exposes layout.json properties to QML
│
├─ ChatBridge (src/utils/chat_bridge.py)
│   ├─ "groq" mode: Python Groq client with conversation history
│   └─ "binary" mode: subprocess call to ./apicomm C binary
│
└─ STTClient (src/utils/stt_client.py)
    └─ ctypes wrapper → libs/stt/libstt.so (PortAudio + Groq Whisper)
```

**Request flow:**

1. Talk button held → `STTController.toggle()` → `libstt.so` records 16kHz mono audio
2. Recording stops → Groq Whisper API transcribes → text returned to `handle_send_text()`
3. Text sent to `ChatBridge` → Groq API returns structured response
4. Response parsed into `EMOTION:` global + `CHUNK|delay|emotion|text` segments
5. Each chunk updates `GuiDisplayModel` → QML animates the matching emotion GIF

## AI Response Format

The system prompt (active version: `prompts.txt`) MUST instruct the model to respond in this sync-chunk format:

```
EMOTION: thinking
CHUNK|500|thinking|Hmm, deixa eu pensar...
CHUNK|300|confident|Sim, é exatamente isso!
```

- `EMOTION:` sets the dominant/global emotion.
- `CHUNK|<delay_ms>|<emotion>|<text>` — each chunk drives one animation frame update.
- `PAUSE:<ms>` — can be used for timed pauses without text.
- Valid emotions: `angry, confident, confused, cool, crying, delicious, embarrassed, funny, happy, kissy, laughing, loving, neutral, relaxed, sad, shocked, silly, sleepy, surprised, thinking, winking`.
- Emotion GIFs live in `assets/emojis/<emotion>.gif`.

## Key Conventions

**Configuration** is JSON-based via `ConfigManager` (singleton).

- Core config: `config/config.json`.
- UI Layout: `config/layout_config.json`.
- Access in Python: `ConfigManager().get("backend", "type")`.
- Access in QML: `lc.get("section", "key")` via `LayoutConfigModel`.

**Display logic**:

- Use `GuiDisplayModel` properties (`statusText`, `emotionPath`, `ttsText`) to trigger QML updates.
- Keep UI logic in QML/Model and business logic in `src/utils/`.

**Async pattern**:

- The app uses `qasync` to bridge Qt's event loop with Python `asyncio`.
- All I/O operations (API, STT) are `async def`. Use `await` for calls.

**Import order** (isort black profile): `FUTURE → STDLIB → THIRDPARTY → FIRSTPARTY (src/) → LOCALFOLDER`.

**Prompting**: Edit `prompts.txt` for behavior changes.

**Native libs**: Graceful fallback in `stt_client.py` if native shared objects fail to load.

## File Locations Quick Reference

| What                 | Where                              |
| -------------------- | ---------------------------------- |
| App entry point      | `main_gui.py`                      |
| QML UI               | `src/display/gui_display.qml`      |
| Python UI Bridge     | `src/display/gui_display_model.py` |
| Chat logic           | `src/utils/chat_bridge.py`         |
| STT wrapper          | `src/utils/stt_client.py`          |
| Configuration        | `config/config.json`               |
| Active system prompt | `prompts.txt`                      |
| VAD Test script      | `vadtest.py`                       |
