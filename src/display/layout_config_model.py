# -*- coding: utf-8 -*-
"""
Layout configuration model for QML data binding.

Loads layout_config.json and exposes every property to QML so that the
gui_display.qml can use configurable values instead of hard-coded ones.
When studio/layout-editor mode is active the values can be changed at
runtime and persisted back to the JSON file.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

_logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "layout_config.json"

# Default layout (mirrors the initial gui_display.qml hard-coded values)
_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "root": {"color": "#f5f5f5"},
    "titleBar": {"height": 36, "color": "#f7f8fa"},
    "statusDot": {
        "width": 8, "height": 8, "radius": 4,
        "colorReady": "#00b42a", "colorListening": "#ff7d00",
        "colorThinking": "#165dff", "colorError": "#f53f3f",
        "colorDefault": "#c9cdd4",
    },
    "statusText": {"fontSize": 11, "color": "#86909c", "maxWidth": 200},
    "btnMin": {
        "width": 24, "height": 24, "radius": 6,
        "colorPressed": "#e5e6eb", "colorHover": "#f2f3f5",
        "colorNormal": "transparent", "iconColor": "#4e5969", "iconSize": 14,
    },
    "btnClose": {
        "width": 24, "height": 24, "radius": 6,
        "colorPressed": "#f53f3f", "colorHover": "#ff7875",
        "colorNormal": "transparent", "iconColor": "#86909c",
        "iconColorHover": "white", "iconSize": 14,
    },
    "contentArea": {"margins": 12, "spacing": 12},
    "emotionArea": {"minimumHeight": 80, "sizeFactor": 0.7, "minSize": 60},
    "emotionGlow": {
        "scaleFactor": 1.2, "colorInner": "#20165dff", "colorOuter": "transparent",
    },
    "ttsArea": {
        "height": 60, "color": "transparent", "textMargins": 10,
        "fontSize": 13, "textColor": "#555555",
    },
    "buttonBar": {
        "height": 72, "color": "#f7f8fa", "margins": 12,
        "bottomMargin": 10, "spacing": 6,
    },
    "autoButton": {
        "preferredWidth": 100, "maxWidth": 140, "height": 38, "radius": 8,
        "colorNormal": "#165dff", "colorHover": "#4080ff",
        "colorPressed": "#0e42d2", "textColor": "white", "fontSize": 12,
    },
    "abortButton": {
        "preferredWidth": 80, "maxWidth": 120, "height": 38, "radius": 8,
        "colorNormal": "#eceff3", "colorHover": "#f2f3f5",
        "colorPressed": "#e5e6eb", "textColor": "#1d2129", "fontSize": 12,
    },
    "textInput": {
        "height": 38, "radius": 8, "bgColor": "white",
        "borderColorFocused": "#165dff", "borderColorNormal": "#e5e6eb",
        "borderWidthFocused": 2, "borderWidthNormal": 1,
        "textColor": "#333333", "placeholderColor": "#c9cdd4",
        "fontSize": 12, "leftMargin": 10, "rightMargin": 10,
    },
    "sendButton": {
        "preferredWidth": 60, "maxWidth": 84, "height": 38, "radius": 8,
        "colorNormal": "#165dff", "colorHover": "#4080ff",
        "colorPressed": "#0e42d2", "colorDisabled": "#a0bfff",
        "textColor": "white", "fontSize": 12,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Return *base* with values from *override* applied on top."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class LayoutConfigModel(QObject):
    """Exposes layout configuration to QML and supports runtime editing."""

    configChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config: Dict[str, Dict[str, Any]] = _deep_merge(_DEFAULTS, {})
        self._studio_mode = False
        self._load()

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _load(self):
        """Load layout_config.json, falling back to built-in defaults."""
        try:
            if _CONFIG_PATH.exists():
                with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self._config = _deep_merge(_DEFAULTS, data)
        except Exception as exc:
            _logger.warning("Failed to load layout config (%s), using defaults", exc)
            self._config = _deep_merge(_DEFAULTS, {})

    def _save(self):
        """Persist current config to layout_config.json."""
        try:
            _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
                json.dump(self._config, fh, indent=4, ensure_ascii=False)
        except Exception as exc:
            _logger.warning("Failed to save layout config: %s", exc)

    # ------------------------------------------------------------------
    # QML-facing API
    # ------------------------------------------------------------------

    @pyqtProperty(bool, notify=configChanged)
    def studioMode(self):
        return self._studio_mode

    @studioMode.setter  # type: ignore[attr-defined]
    def studioMode(self, value):
        if self._studio_mode != value:
            self._studio_mode = value
            self.configChanged.emit()

    @pyqtSlot(str, str, result="QVariant")
    def get(self, section: str, key: str):
        """Return a single layout value.  ``layoutConfig.get("root", "color")``"""
        return self._config.get(section, {}).get(key)

    @pyqtSlot(str, str, "QVariant")
    def set(self, section: str, key: str, value):
        """Set a layout value at runtime and persist."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self._save()
        self.configChanged.emit()

    @pyqtSlot()
    def resetAll(self):
        """Restore every property to built-in defaults and persist."""
        self._config = _deep_merge(_DEFAULTS, {})
        self._save()
        self.configChanged.emit()

    @pyqtSlot(str)
    def resetSection(self, section: str):
        """Restore one section to defaults and persist."""
        if section in _DEFAULTS:
            self._config[section] = dict(_DEFAULTS[section])
            self._save()
            self.configChanged.emit()

    @pyqtSlot(result="QVariant")
    def allSections(self):
        """Return a list of section names."""
        return list(self._config.keys())

    @pyqtSlot(str, result="QVariant")
    def sectionKeys(self, section: str):
        """Return key names for a section."""
        return list(self._config.get(section, {}).keys())
