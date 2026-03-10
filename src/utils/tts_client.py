"""
TTS Client — async HTTP client for the Edge TTS FastAPI server.

Pre-synthesises audio in background tasks so playback is nearly instant
when the chunk_emitter is ready to play.  Playback uses miniaudio in a
worker thread (asyncio.to_thread) so the Qt event-loop never blocks.
"""

import asyncio
import time
from typing import Optional

import aiohttp

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    import miniaudio

    _HAS_MINIAUDIO = True
except ImportError:
    _HAS_MINIAUDIO = False
    logger.warning("miniaudio not installed — TTS playback disabled")


class TTSClient:
    """Lightweight async wrapper around the TTS API server."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        enabled: bool = True,
        voice: str = "pt-BR-FranciscaNeural",
        rate: str = "+15%",
        pitch: str = "+3Hz",
        volume: str = "+0%",
    ):
        self._base_url = base_url.rstrip("/")
        self._enabled = enabled and _HAS_MINIAUDIO
        self._voice = voice
        self._rate = rate
        self._pitch = pitch
        self._volume = volume
        self._session: Optional[aiohttp.ClientSession] = None
        self._audio_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(keepalive_timeout=30, limit=4)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=15),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """GET /health — disables TTS if the server is unreachable."""
        if not self._enabled:
            return False
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/health") as resp:
                if resp.status == 200:
                    logger.info("TTS server healthy at %s", self._base_url)
                    return True
                logger.warning("TTS health check returned %d", resp.status)
        except Exception as exc:
            logger.warning("TTS server unreachable (%s): %s", self._base_url, exc)
        self._enabled = False
        return False

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def pre_synthesize(self, text: str) -> Optional[asyncio.Task]:
        """Fire-and-forget synthesis — returns a Task that resolves to bytes."""
        if not self._enabled or not text.strip():
            return None
        return asyncio.create_task(self._fetch_audio(text))

    async def _fetch_audio(self, text: str) -> Optional[bytes]:
        """POST /synthesize and return the MP3 bytes (or None on error)."""
        try:
            session = await self._get_session()
            payload = {
                "text": text,
                "voice": self._voice,
                "rate": self._rate,
                "pitch": self._pitch,
                "volume": self._volume,
                "stream": False,
            }
            async with session.post(
                f"{self._base_url}/synthesize", json=payload
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("TTS synthesis HTTP %d: %s", resp.status, body[:120])
                    return None
                return await resp.read()
        except Exception as exc:
            logger.warning("TTS fetch error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    async def play(self, audio_bytes: bytes) -> None:
        """Play MP3 bytes through the default output device (no overlap)."""
        if not _HAS_MINIAUDIO or not audio_bytes:
            return
        async with self._audio_lock:
            try:
                await asyncio.to_thread(self._play_sync, audio_bytes)
            except Exception as exc:
                logger.warning("TTS playback error: %s", exc)

    @staticmethod
    def _play_sync(audio_bytes: bytes) -> None:
        """Decode MP3 and play synchronously (runs in a worker thread)."""
        decoded = miniaudio.decode(audio_bytes, output_format=miniaudio.SampleFormat.SIGNED16)
        if not decoded.samples or decoded.num_frames == 0:
            return

        duration_s = decoded.num_frames / decoded.sample_rate
        nch = decoded.nchannels
        samples = decoded.samples
        total = len(samples)
        pos = [0]

        def _generator():
            required = yield b""
            while pos[0] < total:
                n = required * nch
                chunk = samples[pos[0] : pos[0] + n]
                pos[0] += n
                if not chunk:
                    break
                required = yield chunk

        gen = _generator()
        next(gen)

        device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=nch,
            sample_rate=decoded.sample_rate,
        )
        try:
            device.start(gen)
            time.sleep(duration_s + 0.08)
        finally:
            device.close()
