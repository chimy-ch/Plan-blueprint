"""单实例保护：同名互斥体，防止同时运行多个副本（多个托盘图标）。

用法：
    if not single_instance.acquire():
        ...   # 已有实例在运行
    ...
    single_instance.release()
"""

from __future__ import annotations

import ctypes
import sys

IS_WINDOWS = sys.platform == "win32"

MUTEX_NAME = "Local\\BlueprintBlueprint.SingleInstance"
ERROR_ALREADY_EXISTS = 183

if IS_WINDOWS:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

_handle = None


def acquire(name: str = MUTEX_NAME) -> bool:
    """尝试成为唯一实例。返回 True 表示当前进程可以继续启动。"""
    global _handle
    if not IS_WINDOWS:
        return True
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, True, name)
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _handle = handle
    return True


def release() -> None:
    global _handle
    if _handle:
        try:
            kernel32.CloseHandle(_handle)
        except OSError:
            pass
        _handle = None
