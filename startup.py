"""开机自动启动管理。

通过当前用户注册表项
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
写入一个启动项，值为「启动命令」。这样开机后会自动运行本程序，
并以 `--tray` 参数启动（直接最小化到系统托盘）。
"""

from __future__ import annotations

import os
import sys

import paths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "BlueprintBlueprint"
IS_WINDOWS = sys.platform.startswith("win")

try:
    import winreg
except ImportError:  # 非 Windows 平台
    winreg = None  # type: ignore[assignment]


def launch_command() -> str:
    """生成开机启动使用的命令行。"""
    if paths.is_frozen():
        return f'"{os.path.abspath(sys.executable)}" --tray'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    script = os.path.join(paths.APP_DIR, "main.py")
    return f'"{exe}" "{script}" --tray'


def _open_key(access: int):
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)  # type: ignore[union-attr]


def current_command() -> str:
    if winreg is None:
        return ""
    try:
        with _open_key(winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return str(value)
    except OSError:
        return ""


def is_enabled() -> bool:
    if winreg is None:
        return False
    return bool(current_command())


def enable(command: str | None = None) -> bool:
    if winreg is None:
        return False
    value = command or launch_command()
    try:
        with _open_key(winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, value)
        return True
    except OSError:
        return False


def disable() -> bool:
    if winreg is None:
        return False
    try:
        with _open_key(winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def set_enabled(flag: bool, command: str | None = None) -> bool:
    return enable(command) if flag else disable()


def is_current(command: str | None = None) -> bool:
    """注册表里的启动命令是否与当前程序一致。"""
    existing = current_command()
    if not existing:
        return False
    return existing == (command or launch_command())


if __name__ == "__main__":
    print("启动命令:", launch_command())
    print("已启用  :", is_enabled())
    if is_enabled():
        print("注册表值:", current_command())
