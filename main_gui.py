#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal GUI Launcher for Xiaozhi AI Client (GUI-only version)

This launcher starts only the GUI display without any backend services.
Ideal for testing and developing the GUI components in isolation.
"""

import asyncio
import argparse
import json
import sys
import os
import signal
from typing import Optional

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
from src.utils.stt_client import STTClient, STTClientError

logger = get_logger(__name__)


class STTController:
    """Manages the STT lifecycle and ties it to the GUI talk button."""

    def __init__(self, gui_display, send_text_callback, stt_client):
        self._gui_display = gui_display
        self._send_text_callback = send_text_callback
        self._stt_client = stt_client
        self._recording = False
        self._busy = False

    async def toggle(self):
        if self._busy:
            return
        self._busy = True
        try:
            if not self._recording:
                await self._start()
            else:
                await self._stop()
        finally:
            self._busy = False

    async def _start(self, status_text: str = "Listening...", button_text: str = "Stop"):
        await self._gui_display.update_status(status_text, True)
        await self._gui_display.update_button_status(button_text)
        await self._gui_display.update_emotion("listening")
        try:
            logger.info("STT: starting recording")
            await asyncio.to_thread(self._stt_client.start_recording)
        except STTClientError:
            logger.error("STT: start_recording failed", exc_info=True)
            await self._gui_display.update_status("STT unavailable", False)
            await self._gui_display.update_button_status("Talk")
            await self._gui_display.update_emotion("neutral")
            return
        self._recording = True

    async def start_from_wake(self):
        if self._busy or self._recording:
            return
        self._busy = True
        try:
            await self._start("Wake detected, hearing", "Stop hearing")
        finally:
            self._busy = False

    async def _stop(self):
        transcription = ""
        stt_failed = False
        try:
            await self._gui_display.update_status("Transcribing...", True)
            logger.info("STT: stopping recording and transcribing")
            raw_response = (await asyncio.to_thread(self._stt_client.stop_recording)).strip()
            if raw_response:
                logger.info("STT: raw response length=%d", len(raw_response))
                try:
                    payload = json.loads(raw_response)
                    if isinstance(payload, dict):
                        transcription = str(payload.get("text", "")).strip()
                    else:
                        transcription = raw_response
                except json.JSONDecodeError:
                    transcription = raw_response
        except STTClientError:
            stt_failed = True
            logger.error("STT: stop_recording failed", exc_info=True)
            await self._gui_display.update_status("STT failed", False)
        finally:
            self._recording = False
            await self._gui_display.update_button_status("Talk")
            await self._gui_display.update_emotion("neutral")

        if transcription:
            logger.info("STT: parsed transcription length=%d", len(transcription))
            await self._send_text_callback(transcription)
        elif not stt_failed:
            logger.warning("STT: transcription empty")
            await self._gui_display.update_status("Ready", True)

    async def shutdown(self):
        await asyncio.to_thread(self._stt_client.shutdown)


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
            await gui_display.update_emotion("neutral")

            SMALL_REPLY_THRESHOLD = 80
            chunk_queue: asyncio.Queue = asyncio.Queue()
            extra_pause_ms = 0
            final_text = ""
            stream_success = False
            chunks_emitted = False
            last_chunk_emotion: Optional[str] = None

            async def chunk_emitter():
                nonlocal extra_pause_ms
                try:
                    while True:
                        chunk = await chunk_queue.get()
                        if chunk is None:
                            return
                        delay = max(0.0, min(chunk.get("delay", 2.5), 2.5))
                        emotion = chunk.get("emotion")
                        if emotion:
                            await gui_display.update_emotion(emotion)
                        await gui_display.update_text(chunk.get("text", ""))
                        await asyncio.sleep(delay)
                        if extra_pause_ms > 0:
                            await asyncio.sleep(extra_pause_ms / 1000.0)
                            extra_pause_ms = 0
                except asyncio.CancelledError:
                    pass

            emitter_task = asyncio.create_task(chunk_emitter())

            async def on_chunk(chunk_text: str, delay: float, emotion: Optional[str]):
                nonlocal last_chunk_emotion
                nonlocal chunks_emitted
                if chunk_text:
                    chunks_emitted = True
                    last_chunk_emotion = emotion
                    await chunk_queue.put({"text": chunk_text, "delay": delay, "emotion": emotion})

            async def on_control(ctrl: str):
                nonlocal extra_pause_ms
                if ctrl.upper().startswith("PAUSE:"):
                    try:
                        ms = int(ctrl.split(":", 1)[1])
                    except Exception:
                        ms = 300
                    extra_pause_ms += ms

            async def on_emotion(emotion: str):
                # update GUI emotion (file names expect lower-case keys)
                await gui_display.update_emotion(emotion)

            try:
                final_text = await chat_bridge.send_and_stream(
                    text, on_chunk=on_chunk, on_emotion=on_emotion, on_control=on_control
                )
                stream_success = True
                stderr_chunk = await chat_bridge.read_stderr()
                if stderr_chunk:
                    logger.info(stderr_chunk.strip())
                await gui_display.update_status("Ready", True)
            except Exception as exc:
                logger.error(f"Chat error: {exc}", exc_info=True)
                await gui_display.update_status("Chat error", False)
            finally:
                await chunk_queue.put(None)
                try:
                    await emitter_task
                except asyncio.CancelledError:
                    pass
                if not chunks_emitted and stream_success and final_text and len(final_text) <= SMALL_REPLY_THRESHOLD:
                    if last_chunk_emotion:
                        await gui_display.update_emotion(last_chunk_emotion)
                    await gui_display.update_text(final_text)

        stt_controller = None
        try:
            stt_client = STTClient()
            stt_controller = STTController(gui_display, handle_send_text, stt_client)
        except STTClientError:
            logger.error("Failed to initialize native STT support", exc_info=True)

        def schedule_toggle() -> None:
            if stt_controller:
                asyncio.create_task(stt_controller.toggle())
            else:
                logger.warning("Talk feature disabled because the STT library could not be loaded")

        # Set callbacks so GUI input flows into the C backend
        await gui_display.set_callbacks(
            auto_callback=schedule_toggle,
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
            if stt_controller:
                await stt_controller.shutdown()
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
    except RuntimeError as e:
        if "Event loop stopped before Future completed" in str(e):
            logger.info("GUI closed before loop completion")
            exit_code = 0
        else:
            logger.error(f"Program exited with error: {e}", exc_info=True)
            exit_code = 1
    except Exception as e:
        logger.error(f"Program exited with error: {e}", exc_info=True)
        exit_code = 1
    finally:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
