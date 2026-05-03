import json
import uuid
import os
from typing import Any, Dict

from src.utils.logging_config import get_logger
from src.utils.resource_finder import resource_finder

logger = get_logger(__name__)


class ConfigManager:
    """Configuration manager - singleton."""

    _instance = None

    # New Logical Logical Configuration Structure
    DEFAULT_CONFIG = {
        "app": {
            "name": "Mina AI",
            "version": "1.0.0",
            "language": "pt-BR",
            "client_id": None,
            "device_id": None
        },
        "ai": {
            "chat": {
                "default_provider": "groq",
                "providers": {
                    "groq": {
                        "model": "moonshotai/kimi-k2-instruct",
                        "url": "https://api.groq.com/openai/v1/chat/completions"
                    },
                    "openai": {
                        "model": "gpt-4o-mini",
                        "url": "https://api.openai.com/v1/chat/completions"
                    }
                },
                "system_prompt_path": "prompts.txt",
                "history_limit": 10
            },
            "tts": {
                "enabled": True,
                "url": "http://localhost:8000",
                "voice": "pt-BR-FranciscaNeural",
                "rate": "+15%",
                "pitch": "+3Hz",
                "volume": "+0%"
            },
            "stt": {
                "enabled": True,
                "provider": "native",
                "language": "pt-BR"
            }
        },
        "hardware": {
            "audio": {
                "input_device_index": None,
                "output_device_index": None,
                "sample_rate": 16000,
                "channels": 1
            },
            "wake_word": {
                "enabled": True,
                "engine": "porcupine",
                "model_path": "models/porcupine_params_pt.pv",
                "keyword_path": "keywords/abacaxi_linux.ppn",
                "sensitivity": 0.5
            },
            "vad": {
                "enabled": True,
                "model_path": "models/silero_vad.onnx",
                "threshold": 0.5,
                "timeout": 3.0
            },
            "camera": {
                "index": 0,
                "resolution": [640, 480],
                "fps": 30
            }
        },
        "gui": {
            "theme": "dark",
            "fullscreen": False,
            "studio_mode": False,
            "rotation": None,
            "shortcuts": {
                "enabled": True,
                "talk": "ctrl+j",
                "auto": "ctrl+k",
                "abort": "ctrl+q"
            }
        },
        "network": {
            "ota_url": "https://api.tenclass.net/xiaozhi/ota/",
            "auth_url": "https://xiaozhi.me/"
        }
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._init_config_paths()
        self._ensure_required_directories()
        self._config = self._load_config()

    def _init_config_paths(self):
        self.config_dir = resource_finder.find_config_dir()
        if not self.config_dir:
            project_root = resource_finder.get_project_root()
            self.config_dir = project_root / "config"
            self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"

    def _ensure_required_directories(self):
        project_root = resource_finder.get_project_root()
        for d in ["models", "cache", "bin", "libs"]:
            path = project_root / d
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        try:
            if self.config_file.exists():
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
                # If the file is still using the old structure (e.g., has SYSTEM_OPTIONS), we might want to wipe/migrate.
                # For this task, we assume the user wants the new structure.
                if "SYSTEM_OPTIONS" in config:
                    logger.info("Detected old config structure. Migrating to new logical structure...")
                    return self.DEFAULT_CONFIG.copy() # Simplest migration: reset to new default
                return self._merge_configs(self.DEFAULT_CONFIG, config)
            else:
                self._save_config(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Config load error: {e}")
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config: dict) -> bool:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text(
                json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            return True
        except Exception as e:
            logger.error(f"Config save error: {e}")
            return False

    @staticmethod
    def _merge_configs(default: dict, custom: dict) -> dict:
        result = default.copy()
        for key, value in custom.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def get_config(self, path: str, default: Any = None) -> Any:
        try:
            value = self._config
            for key in path.split("."):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def update_config(self, path: str, value: Any) -> bool:
        try:
            current = self._config
            *parts, last = path.split(".")
            for part in parts:
                current = current.setdefault(part, {})
            current[last] = value
            return self._save_config(self._config)
        except Exception as e:
            logger.error(f"Config update error {path}: {e}")
            return False

    def reload_config(self) -> bool:
        self._config = self._load_config()
        return True

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
