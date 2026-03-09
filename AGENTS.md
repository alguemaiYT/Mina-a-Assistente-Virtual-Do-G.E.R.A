# Repository Guidelines & Agent Synchronization

## Core Goal

Maintain the sync between AI response chunks and QML facial animations. Any changes to the AI's persona or response logic must respect the `CHUNK|delay|emotion|text` protocol.

## Module Responsibilities

- `src/display/`: Pure UI and the Python bridge (`GuiDisplayModel`). Do not put API or audio logic here.
- `src/utils/`: All side-effect heavy logic (STT, Chat, Config, Wake Word).
- `assets/emojis/`: Contains GIFs named exactly after the valid emotions.

## Development Workflow

1. **Frontend updates**: Modify `gui_display.qml`. Use `--studio` mode for layout tweaks.
2. **Backend/AI updates**: Modify `chat_bridge.py` or the `prompts.txt` system prompt.
3. **Native logic**: Modify `stt.c` or `apicomm.c` and recompile for the target OS (Windows/Linux).

## Conventions for AI Agents

- **Emotional Palette**: When suggesting responses or prompts, always use one of the 22 valid emotions.
- **Async Safety**: Always use `asyncio` for I/O. Use `qasync` to wrap the Qt loop.
- **Config Access**: Use `ConfigManager` instead of reading JSON files directly.
- **Portuguese (PT-BR)**: All user-facing text and AI personality must be in Brazilian Portuguese.

## Common Pitfalls

- **Missing DLLs/SOs**: If STT doesn't work, check if `libs/stt/` contains the correct binary for the OS.
- **PortAudio conflicts**: Ensure no other app is monopolizing the mic during development.
- **Chunk Timing**: Keep `delay_ms` in chunks between 200ms and 2000ms for natural flow.
