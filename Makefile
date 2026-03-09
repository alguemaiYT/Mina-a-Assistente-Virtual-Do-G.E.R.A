.DEFAULT_GOAL := help

PYTHON ?= python
PIP ?= $(PYTHON) -m pip

.PHONY: help install install-mac run run-fullscreen run-studio lint format sort-imports check test stt-linux

help:
	@echo Available targets:
	@echo   install         Install runtime dependencies from requirements.txt
	@echo   install-mac     Install macOS-specific dependencies
	@echo   run             Start the GUI launcher
	@echo   run-fullscreen  Start the GUI launcher in fullscreen mode
	@echo   run-studio      Start the GUI launcher in studio/layout-editor mode
	@echo   lint            Run Flake8 across the repository
	@echo   format          Format Python files with Black
	@echo   sort-imports    Sort Python imports with isort
	@echo   check           Run a lightweight syntax smoke test with compileall
	@echo   test            Alias for check (the repo has no automated test suite yet)
	@echo   stt-linux       Build the optional Linux STT shared library

install:
	$(PIP) install -r requirements.txt

install-mac:
	$(PIP) install -r requirements_mac.txt

run:
	$(PYTHON) main_gui.py

run-fullscreen:
	$(PYTHON) main_gui.py -f

run-studio:
	$(PYTHON) main_gui.py -s

lint:
	$(PYTHON) -m flake8 .

format:
	$(PYTHON) -m black .

sort-imports:
	$(PYTHON) -m isort .

check:
	$(PYTHON) -m compileall main_gui.py src

test: check

stt-linux:
	gcc -shared -fPIC stt.c -o libs/stt/libstt.so -lportaudio -lcurl
