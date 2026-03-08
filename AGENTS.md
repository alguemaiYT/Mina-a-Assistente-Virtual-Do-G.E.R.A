# Repository Guidelines

## Project Structure & Module Organization
- `main_gui.py` is the GUI entry point for local development.
- Core application code lives under `src/`:
  - `src/display/` for QML display integration (`gui_display.py`, `gui_display.qml`).
  - `src/views/` for activation/settings windows and reusable UI components.
  - `src/utils/` for config, logging, chat bridge, wake-word, and helper utilities.
- Static resources are in `assets/` (images/emojis), runtime config in `config/`, and bundled native libs/models in `libs/` and `models/`.
- Keep generated/runtime artifacts (`logs/`, `cache/`) out of feature commits unless debugging requires them.

## Build, Test, and Development Commands
- Install dependencies: `pip install -r requirements.txt`
- Start the app locally: `python main_gui.py`
- Optional macOS dependency set: `pip install -r requirements_mac.txt`
- Format imports/code (when tools are installed):
  - `black .`
  - `isort .`
- There is no packaging/build pipeline in this fork; development is run-in-place from the repository root.

## Coding Style & Naming Conventions
- Python style follows `pyproject.toml`: Black with line length `88`, `isort` profile `black`.
- Use 4-space indentation and type hints where practical for public methods.
- Prefer `snake_case` for Python functions/files, `PascalCase` for classes, and descriptive QML helper names.
- Keep UI logic in `src/views/` or `src/display/`; move shared non-UI behavior into `src/utils/`.

## Testing Guidelines
- No formal automated test suite is currently checked in (`tests/` is absent).
- Validate changes with a local smoke run: `python main_gui.py` and verify the affected screen/flow.
- For audio/VAD-related edits, run targeted scripts such as `python vadtest.py` when relevant.
- If you add tests, place them in a new `tests/` directory and name files `test_<feature>.py`.

## Commit & Pull Request Guidelines
- Recent history mixes generic and Conventional Commit styles; prefer Conventional Commits (`feat:`, `fix:`, `chore:`) with a concise scope.
- Keep commits focused (one behavior change per commit) and avoid unrelated formatting churn.
- PRs should include:
  - Clear problem/solution summary.
  - Linked issue (if applicable).
  - Screenshots or short recordings for GUI/QML changes.
  - Manual verification steps (exact commands and what was validated).

## Security & Configuration Tips
- Do not commit secrets (for example `GROQ_API_KEY`) or machine-specific tokens.
- Keep local overrides in environment variables; treat `config/config.json` edits as intentional and reviewable.
