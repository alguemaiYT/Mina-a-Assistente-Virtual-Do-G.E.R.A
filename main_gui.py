#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal GUI Launcher for Xiaozhi AI Client (GUI-only version)

This launcher starts only the GUI display without any backend services.
Ideal for testing and developing the GUI components in isolation.
"""

import asyncio
import argparse
import sys
import os
import signal

# Configure Qt platform before importing Qt
is_wayland = (
    os.environ.get("WAYLAND_DISPLAY")
    or os.environ.get("XDG_SESSION_TYPE") == "wayland"
)

if is_wayland and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
    os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")

try:
    import qasync
    from PyQt5.QtWidgets import QApplication
except ImportError as e:
    print(f"ERROR: GUI mode requires qasync and PyQt5: {e}")
    print("Please install: pip install PyQt5 qasync")
    sys.exit(1)

from src.display.gui_display import GuiDisplay
from src.utils.chat_bridge import ChatBridge
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def _parse_cli_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-f", "--fullscreen", action="store_true")
    args, remaining = parser.parse_known_args(sys.argv[1:])
    sys.argv = [sys.argv[0]] + remaining
    return args.fullscreen


async def run_gui(fullscreen: bool = False):
    """
    Run the GUI display in standalone mode.
    """
    logger.info("Starting Xiaozhi GUI (standalone mode)")
    
    try:
        chat_bridge = ChatBridge()

        # Create and start the GUI display
        gui_display = GuiDisplay()
        if fullscreen:
            gui_display.set_force_fullscreen(True)

        async def handle_send_text(text: str):
            """Send text to the C chat engine and stream tokens back to the GUI."""
            await gui_display.update_status("Thinking...", True)
            await gui_display.update_text("")

            current_text = ""

            async def on_token(chunk: str):
                nonlocal current_text
                current_text += chunk
                await gui_display.update_text(current_text)

            async def on_emotion(emotion: str):
                # update GUI emotion (file names expect lower-case keys)
                await gui_display.update_emotion(emotion)

            try:
                await chat_bridge.send_and_stream(text, on_token=on_token, on_emotion=on_emotion)
                stderr_chunk = await chat_bridge.read_stderr()
                if stderr_chunk:
                    logger.info(stderr_chunk.strip())
                await gui_display.update_status("Ready", True)
            except Exception as exc:
                logger.error(f"Chat error: {exc}", exc_info=True)
                await gui_display.update_status("Chat error", False)

        # Set callbacks so GUI input flows into the C backend
        await gui_display.set_callbacks(
            auto_callback=lambda: logger.info("Auto mode toggled"),
            abort_callback=lambda: logger.info("Aborted"),
            send_text_callback=handle_send_text,
        )
        
        # Start the GUI
        await gui_display.start()
        
        # Set initial status
        await gui_display.update_status("GUI Ready (C backend)", True)
        await gui_display.update_emotion("neutral")
        
        logger.info("GUI started successfully")
        
        # Keep the event loop running until GUI is closed
        try:
            while gui_display._running:
                await asyncio.sleep(0.1)
        finally:
            await chat_bridge.stop()
            
    except Exception as e:
        logger.error(f"GUI error: {e}", exc_info=True)
        return 1
    
    return 0


def main():
    """
    Main entry point for the GUI-only launcher.
    """
    exit_code = 1
    
    try:
        # Setup logging
        setup_logging()
        
        # Handle signals
        try:
            if hasattr(signal, "SIGTRAP"):
                signal.signal(signal.SIGTRAP, signal.SIG_IGN)
        except Exception:
            pass
        
        fullscreen = _parse_cli_args()
        # Create Qt application
        qt_app = QApplication.instance() or QApplication(sys.argv)
        qt_app.setQuitOnLastWindowClosed(False)
        
        # Create qasync event loop
        loop = qasync.QEventLoop(qt_app)
        asyncio.set_event_loop(loop)
        logger.info("Created qasync event loop")
        
        # Run the GUI
        with loop:
            exit_code = loop.run_until_complete(run_gui(fullscreen=fullscreen))
            
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
        exit_code = 0
    except Exception as e:
        logger.error(f"Program exited with error: {e}", exc_info=True)
        exit_code = 1
    finally:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
