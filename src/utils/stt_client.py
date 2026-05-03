"""Python binding for the C-based STT helper that drives PortAudio + Groq."""

import ctypes
import logging
import os
import platform
from pathlib import Path
from typing import Optional


from src.utils.binary_manager import binary_manager

class STTClientError(RuntimeError):
    """Raised when the native STT helper cannot perform an action."""


class STTClient:
    """Wrapper around the native shared library exported by stt.c."""

    def __init__(self, lib_path: Optional[str] = None):
        self._logger = logging.getLogger(__name__)
        self._lib = None
        self._lib_path = None
        
        try:
            self._lib_path = Path(lib_path) if lib_path else binary_manager.ensure_stt_lib()
        except Exception as e:
            self._logger.error("Failed to ensure STT library: %s", e)
            self._lib_path = None

        if not self._lib_path or not self._lib_path.exists():
            self._logger.error("STT library not found or failed to compile. STT features will be disabled.")
            return

        try:
            self._lib = ctypes.CDLL(str(self._lib_path))
            self._configure_prototypes()

            if self._lib.stt_initialize() != 0:
                self._logger.error("Native STT initialization failed")
                self._lib = None
        except Exception as e:
            self._logger.error("Failed to load STT library: %s", e)
            self._lib = None

    def _configure_prototypes(self) -> None:
        if not self._lib:
            return
        self._lib.stt_initialize.restype = ctypes.c_int
        self._lib.stt_start_recording.restype = ctypes.c_int
        self._lib.stt_stop_recording_and_transcribe.restype = ctypes.c_void_p
        self._lib.stt_free_transcription.argtypes = [ctypes.c_void_p]
        self._lib.stt_is_recording.restype = ctypes.c_int
        self._lib.stt_shutdown.restype = None

    def start_recording(self) -> None:
        """Begin a new STT capture session."""
        if not self._lib:
            self._logger.warning("STT: Library not loaded, ignoring start_recording")
            return
        self._logger.info("Starting STT recording")
        if self._lib.stt_start_recording() != 0:
            self._logger.error("Native STT start_recording returned failure")

    def stop_recording(self) -> str:
        """Stop the capture and return the transcription (empty if nothing captured)."""
        if not self._lib:
            self._logger.warning("STT: Library not loaded, ignoring stop_recording")
            return ""
        self._logger.info("Stopping STT recording")
        ptr = self._lib.stt_stop_recording_and_transcribe()
        if not ptr:
            self._logger.warning("Native STT returned no transcription")
            return ""

        raw = ctypes.cast(ptr, ctypes.c_char_p).value
        transcription = raw.decode("utf-8", errors="ignore") if raw else ""
        self._logger.info("Transcription received (%d chars)", len(transcription))
        self._lib.stt_free_transcription(ptr)
        return transcription

    def is_recording(self) -> bool:
        """Answers whether a recording run is in progress."""
        if not self._lib:
            return False
        return bool(self._lib.stt_is_recording())

    def shutdown(self) -> None:
        """Release native resources (PortAudio + curl)."""
        if not self._lib:
            return
        self._logger.info("Shutting down native STT")
        self._lib.stt_shutdown()

    def __del__(self) -> None:
        try:
            self.shutdown()
        except Exception:
            pass
