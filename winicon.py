"""Windows 窗口与任务栏图标辅助（纯 ctypes，无第三方依赖）。

Tkinter 的 `wm iconbitmap` 只会把图标以单一尺寸交给窗口，导致：
  · 任务栏在高 DPI 下需要 48x48 的 ICON_BIG，却拿到 32x32 拉伸版，图标发虚；
  · 由 pythonw.exe 启动时，任务栏按钮可能沿用 Python 自己的图标。

本模块分别按系统大/小图标尺寸载入 blueprint.ico，并设置显式 AppUserModelID。
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

AUMID = "Blueprint.PlanFlow.Desktop"
APP_ID_PATH = rf"Software\Classes\AppUserModelId\{AUMID}"

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
GCLP_HICON = -14
GCLP_HICONSM = -34
SM_CXICON, SM_CYICON = 11, 12
SM_CXSMICON, SM_CYSMICON = 49, 50

_user32 = ctypes.windll.user32 if IS_WINDOWS else None
_shell32 = ctypes.windll.shell32 if IS_WINDOWS else None

if IS_WINDOWS:
    _user32.LoadImageW.restype = wintypes.HANDLE
    _user32.LoadImageW.argtypes = (
        wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    )
    _user32.SendMessageW.restype = wintypes.LPARAM
    _user32.SendMessageW.argtypes = (
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    )
    _user32.GetSystemMetrics.restype = ctypes.c_int
    _user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _user32.SetClassLongPtrW.restype = ctypes.c_void_p
        _user32.SetClassLongPtrW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_void_p)
        _set_class_long = _user32.SetClassLongPtrW
    else:
        _user32.SetClassLongW.restype = wintypes.DWORD
        _user32.SetClassLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.DWORD)
        _set_class_long = _user32.SetClassLongW


def set_app_user_model_id(app_id: str = AUMID) -> bool:
    """设置显式 AppUserModelID。必须在创建 Tk 根窗口之前调用。"""
    if not IS_WINDOWS:
        return False
    try:
        _shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
        return True
    except (AttributeError, OSError):
        return False


def register_app_id(icon_path: str, display_name: str, app_id: str = AUMID) -> bool:
    """在注册表登记本应用的显示名与图标，供任务栏/跳转列表使用。"""
    if not IS_WINDOWS:
        return False
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_ID_PATH) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, display_name)
            if icon_path and os.path.exists(icon_path):
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon_path)
        return True
    except OSError:
        return False


def _load_icon(path: str, size: int):
    return _user32.LoadImageW(None, path, IMAGE_ICON, size, size, LR_LOADFROMFILE)


def _window_handles(root) -> list[int]:
    handles: list[int] = []
    for getter in ("wm_frame", "winfo_id"):
        try:
            value = getattr(root, getter)()
        except Exception:
            continue
        try:
            hwnd = int(value, 16) if isinstance(value, str) else int(value)
        except (TypeError, ValueError):
            continue
        if hwnd and hwnd not in handles:
            handles.append(hwnd)
    return handles


def apply_window_icon(root, ico_path: str) -> bool:
    """按系统大/小图标尺寸分别为窗口设置 ICON_BIG 与 ICON_SMALL。"""
    if not IS_WINDOWS or not ico_path or not os.path.exists(ico_path):
        return False

    big = _user32.GetSystemMetrics(SM_CXICON)
    small = _user32.GetSystemMetrics(SM_CXSMICON)
    hicon_big = _load_icon(ico_path, big) or _load_icon(ico_path, 0)
    hicon_small = _load_icon(ico_path, small) or hicon_big
    if not hicon_big and not hicon_small:
        return False

    applied = False
    for hwnd in _window_handles(root):
        if hicon_big:
            _user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            _set_class_long(hwnd, GCLP_HICON, hicon_big)
            applied = True
        if hicon_small:
            _user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            _set_class_long(hwnd, GCLP_HICONSM, hicon_small)
            applied = True
    return applied
