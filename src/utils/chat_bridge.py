import asyncio
import json
import os
from typing import Awaitable, Callable, Optional

import aiohttp

from src.utils.binary_manager import binary_manager
from src.utils.config_manager import ConfigManager

TOKEN_END = "<<END>>"
MAX_HISTORY = 10


class ChatBridge:
    """Runs the apicomm C binary or Groq chat stream to callbacks."""

    def __init__(self, binary_path: Optional[str] = None, backend: Optional[str] = None):
        cfg = ConfigManager()
        
        # Determine the active provider
        self.backend = (backend or os.getenv("CHAT_BACKEND") or cfg.get_config("ai.chat.default_provider", "groq")).lower()
        
        if self.backend in ("binary", "apicomm"):
            # If backend is binary, we still need to know which provider it will use internally (usually groq)
            self.backend = "binary"
            provider_name = "groq"
        else:
            provider_name = self.backend

        # Resolve model based on provider
        providers = cfg.get_config("ai.chat.providers", {})
        provider_cfg = providers.get(provider_name, {})
        
        self.chat_model = os.getenv("GROQ_CHAT_MODEL") or provider_cfg.get("model", "moonshotai/kimi-k2-instruct")
        self.api_url = provider_cfg.get("url", "https://api.groq.com/openai/v1/chat/completions")

        if self.backend == "binary":
            path = binary_manager.ensure_apicomm()
            if path:
                self.binary_path = str(path)
            else:
                logger.error("Chat backend set to 'binary' but apicomm could not be found or compiled. Falling back to provider.")
                self.backend = provider_name
                self.binary_path = ""
        else:
            self.binary_path = binary_path or ""
            
        self.proc: Optional[asyncio.subprocess.Process] = None
        self._stdout_buffer = ""
        self._lock = asyncio.Lock()
        self._history = []
        self._system_prompt = self._load_system_prompt()

    async def start(self):
        if self.backend != "binary":
            return
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
        if self.backend != "binary":
            return
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()
        self.proc = None

    def _load_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts.txt")
        if not os.path.exists(prompt_path):
            cfg = ConfigManager()
            return cfg.get_config("ai.chat.system_prompt", "Você é a Mina AI.")
        with open(prompt_path, "r", encoding="utf-8") as prompt_file:
            prompt = prompt_file.read().strip()
        return prompt or "Você é a Mina AI."

    def _append_history(self, role: str, content: str) -> None:
        if not content:
            return
        self._history.append({"role": role, "content": content})
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

    def _build_messages(self, prompt: str) -> list:
        self._append_history("user", prompt)
        messages = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._history)
        return messages

    async def _process_stream_text(
        self,
        text: str,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        on_emotion: Optional[Callable[[str], Awaitable[None]]] = None,
        on_chunk: Optional[Callable[[str, float, Optional[str]], Awaitable[None]]] = None,
        on_control: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        full_response = ""
        self._stdout_buffer += text

        parts = self._stdout_buffer.split("\n")
        self._stdout_buffer = parts[-1]

        for line in parts[:-1]:
            pline = line.strip()
            # sanitize common literal escape sequences so frontend
            # never sees things like "\\n" or "\\r"
            pline = pline.replace("\\n", " ").replace("\\r", " ").strip()

            if not pline:
                continue

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
                return full_response, True

            # handle chunked output with metadata
            if pline.upper().startswith("CHUNK|"):
                fields = pline.split("|", 3)
                if len(fields) == 4:
                    _, delay_str, chunk_emotion, chunk_text = fields
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

        return full_response, False

    async def _send_and_stream_binary(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        on_emotion: Optional[Callable[[str], Awaitable[None]]] = None,
        on_chunk: Optional[Callable[[str, float, Optional[str]], Awaitable[None]]] = None,
        on_control: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
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
            parsed, done = await self._process_stream_text(
                text,
                on_token=on_token,
                on_emotion=on_emotion,
                on_chunk=on_chunk,
                on_control=on_control,
            )
            full_response += parsed
            if done:
                return full_response

        return full_response

    async def _send_and_stream_groq(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        on_emotion: Optional[Callable[[str], Awaitable[None]]] = None,
        on_chunk: Optional[Callable[[str, float, Optional[str]], Awaitable[None]]] = None,
        on_control: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")

        char_model = self.chat_model
        messages = self._build_messages(prompt)

        payload = {
            "model": char_model,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 512,
            "messages": messages,
        }

        full_response = ""
        raw_response = ""
        timeout = aiohttp.ClientTimeout(total=60)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"Groq chat error {resp.status}: {body}")

                while True:
                    line = await resp.content.readline()
                    if not line:
                        break
                    text_line = line.decode("utf-8", errors="ignore").strip()
                    if not text_line:
                        continue
                    if not text_line.startswith("data:"):
                        continue
                    data = text_line[5:].strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if not content:
                        continue
                    raw_response += content
                    parsed, done = await self._process_stream_text(
                        content,
                        on_token=on_token,
                        on_emotion=on_emotion,
                        on_chunk=on_chunk,
                        on_control=on_control,
                    )
                    full_response += parsed
                    if done:
                        break

        if self._stdout_buffer:
            parsed, _ = await self._process_stream_text(
                "\n",
                on_token=on_token,
                on_emotion=on_emotion,
                on_chunk=on_chunk,
                on_control=on_control,
            )
            full_response += parsed

        if raw_response:
            self._append_history("assistant", raw_response)

        return full_response

    async def send_and_stream(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        on_emotion: Optional[Callable[[str], Awaitable[None]]] = None,
        on_chunk: Optional[Callable[[str, float, Optional[str]], Awaitable[None]]] = None,
        on_control: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """Send prompt to the configured backend and stream tokens."""
        async with self._lock:
            self._stdout_buffer = ""
            if self.backend == "binary":
                return await self._send_and_stream_binary(
                    prompt,
                    on_token=on_token,
                    on_emotion=on_emotion,
                    on_chunk=on_chunk,
                    on_control=on_control,
                )
            if self.backend == "groq" or self.backend == "openai":
                return await self._send_and_stream_groq(
                    prompt,
                    on_token=on_token,
                    on_emotion=on_emotion,
                    on_chunk=on_chunk,
                    on_control=on_control,
                )

            raise RuntimeError(f"Unsupported chat backend: {self.backend}")

    async def read_stderr(self) -> str:
        if self.backend != "binary":
            return ""
        if not self.proc or not self.proc.stderr:
            return ""
        try:
            return (await asyncio.wait_for(self.proc.stderr.read(1024), timeout=0.01)).decode(
                "utf-8", errors="ignore"
            )
        except asyncio.TimeoutError:
            return ""
