"""主题系统与用户设置。

- ACCENTS          可选主题色
- build_palette()  由「浅色/深色 + 主题色」生成完整调色板
- Settings         读写「Blueprint configuration file」目录下的 settings.json
"""

from __future__ import annotations

import json
import os

import paths

HERE = paths.APP_DIR
SETTINGS_PATH = paths.SETTINGS_PATH

ACCENTS = (
    ("蓝图蓝", "#2f6bff"),
    ("星河紫", "#8b5cf6"),
    ("青碧", "#0e9f9a"),
    ("苔绿", "#2eaa6a"),
    ("琥珀", "#f08a24"),
    ("绯樱", "#e0457b"),
)

FONT_SIZES = (9, 10, 11, 12)
THEME_LABELS = (("light", "浅色"), ("dark", "深色"))

DEFAULT_SETTINGS = {
    "theme": "light",
    "accent": "#2f6bff",
    "confirm_delete": True,
    "auto_sync_progress": True,
    "highlight_due": True,
    "remember_geometry": True,
    "default_order": "截止日期",
    "font_size": 10,
    "geometry": "",
    "minimize_to_tray": True,
    "close_to_tray": False,
    "hotkey_enabled": True,
}

BOOL_SETTINGS = (
    "confirm_delete",
    "auto_sync_progress",
    "highlight_due",
    "remember_geometry",
    "minimize_to_tray",
    "close_to_tray",
    "hotkey_enabled",
)

LIGHT = {
    "topbar": "#ffffff",
    "bg": "#eef0f8",
    "panel": "#ffffff",
    "panel_alt": "#f5f6fc",
    "statusbar": "#eef0f8",
    "border": "#dcdff0",
    "shadow": "#d5d9ee",
    "text": "#2b3040",
    "muted": "#7a869a",
    "danger": "#d64545",
    "warn": "#e39a1d",
    "ok": "#2eaa6a",
    "heading_bg": "#e6e9f7",
    "heading_fg": "#4a5670",
    "tab_bg": "#e2e5f4",
    "tab_fg": "#5b6784",
    "tab_hover": "#d9ddf0",
    "btn_bg": "#eaeefb",
    "btn_hover": "#dde3f6",
    "btn_fg": "#2b3040",
    "btn_disabled": "#f0f2f9",
    "btn_disabled_fg": "#b3bccd",
    "entry_bg": "#ffffff",
    "entry_border": "#cdd3e8",
    "trough": "#e2e5f4",
    "done_fg": "#9aa4b6",
    "stripe": "#f7f8fe",
}

DARK = {
    "topbar": "#161a33",
    "bg": "#101327",
    "panel": "#1b2044",
    "panel_alt": "#232a52",
    "statusbar": "#161a33",
    "border": "#313a6b",
    "shadow": "#2a3160",
    "text": "#e8ecfb",
    "muted": "#8f9ac6",
    "danger": "#ff6b81",
    "warn": "#f2b23e",
    "ok": "#43d18f",
    "heading_bg": "#262d57",
    "heading_fg": "#b9c2e6",
    "tab_bg": "#1a1f3e",
    "tab_fg": "#98a2cc",
    "tab_hover": "#252c55",
    "btn_bg": "#282f5c",
    "btn_hover": "#343d70",
    "btn_fg": "#e8ecfb",
    "btn_disabled": "#212748",
    "btn_disabled_fg": "#5c6693",
    "entry_bg": "#212852",
    "entry_border": "#3a4374",
    "trough": "#282f5c",
    "done_fg": "#6b76a3",
    "stripe": "#1f2650",
}


# ------------------------------------------------------------------ 颜色工具
def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(color_a: str, color_b: str, ratio: float) -> str:
    """ratio=0 返回 color_a，ratio=1 返回 color_b。"""
    a, b = hex_to_rgb(color_a), hex_to_rgb(color_b)
    return rgb_to_hex(a[i] + (b[i] - a[i]) * ratio for i in range(3))


def lighten(color: str, amount: float) -> str:
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float) -> str:
    return mix(color, "#000000", amount)


def luminance(color: str) -> float:
    r, g, b = hex_to_rgb(color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def readable_fg(color: str) -> str:
    """在给定底色上挑一个可读的文字颜色。"""
    return "#171a2b" if luminance(color) > 0.62 else "#ffffff"


def is_hex_color(value) -> bool:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return False
    try:
        hex_to_rgb(value)
    except ValueError:
        return False
    return True


def accent_name(color: str) -> str:
    for name, value in ACCENTS:
        if value.lower() == str(color).lower():
            return name
    return "自定义"


# ------------------------------------------------------------------ 调色板
def build_palette(mode: str, accent: str) -> dict:
    """生成调色板：浅色/深色基底 + 主题色衍生色。"""
    if mode not in ("light", "dark"):
        mode = "light"
    if not is_hex_color(accent):
        accent = ACCENTS[0][1]

    colors = dict(DARK if mode == "dark" else LIGHT)
    panel = colors["panel"]

    if mode == "dark":
        colors["accent_hover"] = lighten(accent, 0.14)
        colors["accent_press"] = lighten(accent, 0.26)
        colors["accent_soft"] = mix(accent, panel, 0.80)
        colors["accent_dim"] = mix(accent, panel, 0.50)
    else:
        colors["accent_hover"] = darken(accent, 0.12)
        colors["accent_press"] = darken(accent, 0.24)
        colors["accent_soft"] = mix(accent, "#ffffff", 0.88)
        colors["accent_dim"] = mix(accent, "#ffffff", 0.55)

    colors["accent"] = accent
    colors["accent_fg"] = readable_fg(accent)
    colors["accent_border"] = mix(accent, panel, 0.55)
    colors["mode"] = mode
    return colors


# ------------------------------------------------------------------ 用户设置
class Settings:
    """settings.json 的读写与校验。"""

    def __init__(self, path: str = SETTINGS_PATH) -> None:
        self.path = path
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        for key, default in DEFAULT_SETTINGS.items():
            if key in raw:
                self.data[key] = raw[key]
        self._validate()

    def _validate(self) -> None:
        if self.data.get("theme") not in ("light", "dark"):
            self.data["theme"] = DEFAULT_SETTINGS["theme"]
        if not is_hex_color(self.data.get("accent")):
            self.data["accent"] = DEFAULT_SETTINGS["accent"]
        try:
            size = int(self.data.get("font_size", DEFAULT_SETTINGS["font_size"]))
        except (TypeError, ValueError):
            size = DEFAULT_SETTINGS["font_size"]
        self.data["font_size"] = size if size in FONT_SIZES else DEFAULT_SETTINGS["font_size"]
        for key in BOOL_SETTINGS:
            self.data[key] = bool(self.data.get(key, DEFAULT_SETTINGS[key]))
        if not isinstance(self.data.get("geometry"), str):
            self.data["geometry"] = ""

    def save(self) -> None:
        paths.ensure_config_dir()
        try:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value) -> None:
        self.data[key] = value

    def update(self, values: dict) -> None:
        self.data.update(values)

    def reset(self) -> None:
        self.data = dict(DEFAULT_SETTINGS)

    def snapshot(self) -> dict:
        return dict(self.data)
