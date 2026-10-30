"""Local configuration management."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "youtube": {
        "default_language": "en",
        "default_quality": "auto",
        "demo_mode": True,
    },
    "streamlabs": {
        "socket_token": "",
        "fund_bar_enabled": True,
        "fund_label": "Fund",
        "fund_target": 100.0,
        "fund_current": 60.0,
    },
    "chat": {
        "author_badge_background": "#3451A3",
        "author_badge_foreground": "#FFFFFF",
        "max_messages": 300,
    },
}


def _luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def color_contrast_ratio(foreground: str, background: str) -> float:
    first, second = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def config_path() -> Path:
    """Return the standard per-user Chali configuration path."""
    override = os.environ.get("CHALI_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "chali" / "config.json"


def _merge_defaults(value: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("configuration root must be a JSON object")
    merged = dict(defaults)
    for key, default in defaults.items():
        if key in value:
            supplied = value[key]
            merged[key] = _merge_defaults(supplied, default) if isinstance(default, dict) else supplied
    for key, supplied in value.items():
        if key not in merged:
            merged[key] = supplied
    return merged


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or config_path()
    if not target.exists():
        return json.loads(json.dumps(DEFAULTS))
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read configuration at {target}: {exc}") from exc
    return _validate(_merge_defaults(raw, DEFAULTS))


def _validate(config: dict[str, Any]) -> dict[str, Any]:
    youtube = config.get("youtube")
    streamlabs = config.get("streamlabs")
    chat = config.get("chat")
    if not isinstance(youtube, dict) or not isinstance(streamlabs, dict) or not isinstance(chat, dict):
        raise TypeError("youtube, streamlabs, and chat settings must be JSON objects")
    for key in ("default_language", "default_quality"):
        if not isinstance(youtube.get(key), str):
            raise TypeError(f"youtube.{key} must be a string")
    for key in ("demo_mode",):
        if not isinstance(youtube.get(key), bool):
            raise TypeError(f"youtube.{key} must be a boolean")
    for key in ("fund_bar_enabled",):
        if not isinstance(streamlabs.get(key), bool):
            raise TypeError(f"streamlabs.{key} must be a boolean")
    for key in ("author_badge_background", "author_badge_foreground"):
        color = chat.get(key)
        if not isinstance(color, str) or len(color) != 7 or color[0] != "#":
            raise ValueError(f"chat.{key} must be a #RRGGBB color")
        try:
            int(color[1:], 16)
        except ValueError as exc:
            raise ValueError(f"chat.{key} must be a #RRGGBB color") from exc
    ratio = color_contrast_ratio(
        chat["author_badge_foreground"], chat["author_badge_background"]
    )
    if ratio < 4.5:
        raise ValueError("chat badge colors must have a contrast ratio of at least 4.5:1")
    for key in ("fund_target", "fund_current"):
        value = streamlabs.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"streamlabs.{key} must be a non-negative number")
    if not isinstance(streamlabs.get("socket_token"), str):
        raise TypeError("streamlabs.socket_token must be a string")
    if not isinstance(streamlabs.get("fund_label"), str):
        raise TypeError("streamlabs.fund_label must be a string")
    if isinstance(chat.get("max_messages"), bool) or not isinstance(chat.get("max_messages"), int):
        raise TypeError("chat.max_messages must be an integer")
    if chat["max_messages"] < 10:
        raise ValueError("chat.max_messages must be an integer of at least 10")
    return config


def save_config(config: dict[str, Any], path: Path | None = None) -> Path:
    target = path or config_path()
    validated = _validate(_merge_defaults(config, DEFAULTS))
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        target.parent.chmod(0o700)
    except OSError:
        pass
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    try:
        temporary.chmod(0o600)
        temporary.replace(target)
        target.chmod(0o600)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return target
