import asyncio
import os
from typing import Awaitable, Callable, Optional

TOKEN_END = "<<END>>"


class ChatBridge:
    """Runs the apicomm C binary and streams tokens to callbacks."""

    def __init__(self, binary_path: Optional[str] = None):
        self.binary_path = binary_path or os.path.join(os.path.dirname(__file__), "..", "..", "apicomm")
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._stdout_buffer = ""
        self._lock = asyncio.Lock()

    async def start(self):
        if self.proc and self.proc.returncode is None:
            return
        try:
            self.proc = await asyncio.create_subprocess_exec(
                self.binary_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"apicomm binary not found at {self.binary_path}") from exc

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()
        self.proc = None

    async def send_and_stream(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        on_emotion: Optional[Callable[[str], Awaitable[None]]] = None,
        on_chunk: Optional[Callable[[str, float, Optional[str]], Awaitable[None]]] = None,
        on_control: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Send prompt to the C process and stream tokens; returns full text."""
        async with self._lock:
            await self.start()
            assert self.proc and self.proc.stdin and self.proc.stdout

            self.proc.stdin.write((prompt + "\n").encode("utf-8"))
            await self.proc.stdin.drain()

            full_response = ""

            while True:
                if self.proc.returncode is not None:
                    break
                chunk = await self.proc.stdout.read(256)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="ignore")
                self._stdout_buffer += text

                # split into lines, keep last partial
                parts = self._stdout_buffer.split('\n')
                self._stdout_buffer = parts[-1]

                for line in parts[:-1]:
                    pline = line.strip()
                    # sanitize common literal escape sequences so frontend
                    # never sees things like "\\n" or "\\r"
                    pline = pline.replace('\\n', ' ').replace('\\r', ' ').strip()

                    # handle emotion parameter lines: EMOTION:<name>
                    if pline.upper().startswith("EMOTION:"):
                        emotion = pline.split(":", 1)[1].strip()
                        if on_emotion and emotion:
                            await on_emotion(emotion)
                        continue

                    # handle control lines like PAUSE:<ms>
                    if pline.upper().startswith("PAUSE:"):
                        if on_control:
                            await on_control(pline)
                        # do not include pause lines in the textual response
                        continue

                    # check sentinel
                    if pline == TOKEN_END:
                        return full_response

                    # handle chunked output with metadata
                    if pline.upper().startswith("CHUNK|"):
                        parts = pline.split("|", 3)
                        if len(parts) == 4:
                            _, delay_str, chunk_emotion, chunk_text = parts
                            try:
                                delay = float(delay_str)
                            except ValueError:
                                delay = 2.5
                            chunk_text = chunk_text.strip()
                            if chunk_text:
                                full_response += chunk_text
                                if on_chunk:
                                    await on_chunk(chunk_text, delay, chunk_emotion.strip() or None)
                        continue

                    # regular text line
                    if pline:
                        full_response += pline
                        if on_token:
                            await on_token(pline)

            return full_response

    async def read_stderr(self) -> str:
        if not self.proc or not self.proc.stderr:
            return ""
        try:
            return (await asyncio.wait_for(self.proc.stderr.read(1024), timeout=0.01)).decode(
                "utf-8", errors="ignore"
            )
        except asyncio.TimeoutError:
            return ""
