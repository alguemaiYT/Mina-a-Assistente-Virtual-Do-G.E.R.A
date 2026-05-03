.DEFAULT_GOAL := help

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
CC ?= gcc

# Architecture detection
ARCH ?= $(shell uname -m | tr '[:upper:]' '[:lower:]')
ifeq ($(ARCH),aarch64)
    ARCH = arm64
endif
ifeq ($(ARCH),i386)
    ARCH = x86
endif
ifeq ($(ARCH),i686)
    ARCH = x86
endif

# Output directories
BIN_DIR = bin/$(ARCH)
LIB_DIR = libs/$(ARCH)

# Target names
APICOMM_BIN = $(BIN_DIR)/apicomm
STT_LIB_NAME = stt
ifeq ($(OS),Windows_NT)
    STT_LIB = $(LIB_DIR)/$(STT_LIB_NAME).dll
    EXE_EXT = .exe
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        STT_LIB = $(LIB_DIR)/lib$(STT_LIB_NAME).dylib
    else
        STT_LIB = $(LIB_DIR)/lib$(STT_LIB_NAME).so
    endif
    EXE_EXT =
endif

APICOMM_OUT = $(BIN_DIR)/apicomm$(EXE_EXT)

.PHONY: help install install-mac run run-fullscreen run-studio lint format sort-imports check test install-deps compile apicomm clean stt-linux stt-windows stt-mac all dirs

help:
	@echo "Available targets:"
	@echo "  install        Install Python dependencies"
	@echo "  install-mac    Install macOS-specific dependencies"
	@echo "  run            Launch the GUI"
	@echo "  run-fullscreen Launch the GUI in fullscreen"
	@echo "  run-studio     Launch the GUI in studio/layout mode"
	@echo "  lint           Run Flake8"
	@echo "  format         Run Black"
	@echo "  sort-imports   Run isort"
	@echo "  check          Run python -m compileall to validate syntax"
	@echo "  test           Alias for check"
	@echo "  install-deps   Install system deps (Debian/Ubuntu)"
	@echo "  compile        Builds apicomm for current arch"
	@echo "  apicomm        Compile apicomm.c for $(ARCH)"
	@echo "  stt-linux      Build $(STT_LIB) for Linux"
	@echo "  stt-windows    Build $(STT_LIB) for Windows"
	@echo "  stt-mac        Build $(STT_LIB) for macOS"
	@echo "  all            install-deps + compile"

dirs:
	mkdir -p $(BIN_DIR) $(LIB_DIR)

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

install-deps:
	@echo "Installing system dependencies on Debian/Ubuntu..."
	apt-get update
	apt-get install -y libcjson-dev libcurl4-openssl-dev libportaudio2

compile: dirs apicomm

apicomm: apicomm.c dirs
	@echo "Compiling apicomm for $(ARCH)..."
	$(CC) -O2 -march=native -Wall -Wextra -o $(APICOMM_OUT) apicomm.c -lcurl -lcjson
	@ls -lh $(APICOMM_OUT)

clean:
	@echo "Cleaning binaries..."
	rm -rf bin/ libs/*/libstt.so libs/*/stt.dll libs/*/libstt.dylib apicomm stt *.o

stt-linux: dirs
	@echo "Building STT helper for Linux ($(ARCH))..."
	$(CC) -shared -fPIC stt.c -o $(STT_LIB) -lportaudio -lcurl

stt-windows: dirs
	@echo "Building STT helper for Windows ($(ARCH))..."
	$(CC) -shared -fPIC stt.c -o $(STT_LIB) -lportaudio -lcurl

stt-mac: dirs
	@echo "Building STT helper for macOS ($(ARCH))..."
	$(CC) -shared -fPIC stt.c -o $(STT_LIB) -lportaudio -lcurl

