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
pip install -r requirements.txt        # Linux/Windows
pip install -r requirements_mac.txt   # macOS

# Code formatting & linting
black .
isort .
flake8
```

There is no test suite.

**Required environment variables:**
```bash
export GROQ_API_KEY="..."        # Groq Whisper (STT) + chat API
export CHAT_BACKEND="groq"       # "groq" (Python) or "binary" (C apicomm)
```

**Recompile C shared libraries if modified:**
```bash
gcc -shared -fPIC stt.c -o libs/stt/libstt.so -lportaudio -lcurl
gcc -shared -fPIC apicomm.c -o libs/apicomm/libapicomm.so -lcurl
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

The system prompt (active version: `prompts.txt`) instructs the model to respond in this format:

```
EMOTION: thinking
CHUNK|500|thinking|Hmm, deixa eu pensar...
CHUNK|300|confident|Sim, é exatamente isso!
```

- `EMOTION:` sets the dominant/global emotion
- `CHUNK|<delay_ms>|<emotion>|<text>` — each chunk drives one animation frame
- Valid emotions: `angry, confident, confused, cool, crying, delicious, embarrassed, funny, happy, kissy, laughing, loving, neutral, relaxed, sad, shocked, silly, sleepy, surprised, thinking, winking`
- Emotion GIFs live in `assets/emojis/<emotion>.gif`
- Change emotion per-chunk only for intentional tone shifts; inherit global emotion otherwise

## Key Conventions

**Configuration** is JSON-based via `ConfigManager` (singleton). Keys are accessed as nested dicts. The config file is `config/config.json`. Layout properties come from `config/layout_config.json`.

**Display callbacks** are injected into `GuiDisplay` at construction time in `main_gui.py`. Do not add direct coupling between display and business logic.

**Async pattern**: The app uses `qasync` to bridge Qt's event loop with Python asyncio. All I/O-bound operations (API calls, STT) are `async def`. The Qt signal/slot system is used for thread-safe GUI updates.

**STT library loading** is graceful: if `libstt.so` fails to load, the app continues with the talk button disabled. Check `stt_client.py` for the fallback path logic.

**Import order** enforced by isort (black profile): `FUTURE → STDLIB → THIRDPARTY → FIRSTPARTY (src/) → LOCALFOLDER`.

**Code style**: Black, line length 88, target Python 3.9+.

**Prompt versioning**: `prompts.txt` is the active prompt. `promptv1.txt`–`promptv3.txt` are historical versions kept for reference. Edit `prompts.txt` (or the string in `chat_bridge.py`) to change Mina's personality/behavior.

**Porcupine wake word** uses Portuguese `.ppn` keyword files from `keywords/keyword_files_pt/` and a Portuguese language model `models/porcupine_params_pt.pv`. Wake word is triggered before STT recording begins when not in manual-button mode.

## File Locations Quick Reference

| What | Where |
|------|-------|
| App entry point | `main_gui.py` |
| QML UI | `src/display/gui_display.qml` |
| Chat logic | `src/utils/chat_bridge.py` |
| STT wrapper | `src/utils/stt_client.py` |
| Configuration | `config/config.json` |
| Emotion GIFs | `assets/emojis/*.gif` |
| C source (STT) | `stt.c`, `stt.h` |
| C source (chat) | `apicomm.c` |
| Active system prompt | `prompts.txt` |
