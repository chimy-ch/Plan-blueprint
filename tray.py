"""系统托盘图标与全局热键（纯 ctypes 实现，不依赖第三方库）。

设计要点：
  · 单独的守护线程创建隐藏窗口 + 消息循环，负责 Shell_NotifyIconW 托盘图标
    与 RegisterHotKey 全局热键；
  · 所有 Tk 操作仍由主线程完成，线程间只通过 threading.Event 通信，保证线程安全。

主线程用法：
    tray = TrayService(icon_path, "提示文字", hotkey_enabled=True)
    tray.start()
    if tray.hotkey_event.is_set(): ...      # 轮询
    tray.notify("标题", "内容")
    tray.stop()
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading

IS_WINDOWS = sys.platform == "win32"

WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_TRAYNOTIFY = WM_APP + 2
WM_HOTKEY = 0x0312
WM_COMMAND = 0x0111
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_J = 0x4A
HOTKEY_ID = 0xB1

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
SM_CXSMICON = 49
SM_CYSMICON = 50
IDI_APPLICATION = 32512

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

IDM_OPEN = 1001
IDM_HIDE = 1002
IDM_QUIT = 1003

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

WM_ACTIVATE = WM_APP + 3
TRAY_WINDOW_CLASS = "BlueprintTrayWindow"

HOTKEY_LABEL = "Ctrl+Alt+J"


if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", ctypes.c_byte * 16),
            ("hBalloonIcon", wintypes.HICON),
        ]

    user32.DefWindowProcW.restype = LRESULT
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.GetMessageW.restype = ctypes.c_int
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                   wintypes.UINT, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                  ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadIconW.restype = wintypes.HICON
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT,
                                   ctypes.c_size_t, wintypes.LPCWSTR]
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                      ctypes.c_void_p]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                ctypes.POINTER(wintypes.DWORD)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD,
                                          ctypes.POINTER(NOTIFYICONDATAW)]


def foreground_window() -> int:
    """返回前台窗口句柄（非 Windows 返回 0）。"""
    if not IS_WINDOWS:
        return 0
    return int(user32.GetForegroundWindow() or 0)


def window_process_id(hwnd: int) -> int:
    """返回窗口所属进程 ID。"""
    if not IS_WINDOWS or not hwnd:
        return 0
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def _find_tray_window():
    if not IS_WINDOWS:
        return 0
    try:
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        return user32.FindWindowW(TRAY_WINDOW_CLASS, None)
    except (OSError, AttributeError):
        return 0


def tray_window_exists() -> bool:
    """是否已有另一个实例的托盘窗口存在。"""
    try:
        return bool(_find_tray_window())
    except OSError:
        return False


def wake_existing_instance() -> bool:
    """请求已运行的实例把主窗口显示到前台。"""
    hwnd = _find_tray_window()
    if not hwnd:
        return False
    try:
        user32.PostMessageW(hwnd, WM_ACTIVATE, 0, 0)
    except OSError:
        return False
    return True


class TrayService:
    """托盘图标 + 全局热键服务（在后台线程运行）。"""

    def __init__(self, icon_path: str = "", tooltip: str = "蓝图 Blueprint",
                 hotkey_enabled: bool = True) -> None:
        self.icon_path = icon_path
        self.tooltip = tooltip[:127]
        self.hotkey_enabled = hotkey_enabled

        self.hotkey_event = threading.Event()
        self.open_event = threading.Event()
        self.hide_event = threading.Event()
        self.quit_event = threading.Event()
        self.started = threading.Event()

        self.available = False
        self.hotkey_ok = False
        self.error = ""
        self.hotkey_error = 0

        self.activate_event = threading.Event()

        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._hicon = None
        self._nid: NOTIFYICONDATAW | None = None
        self._wndproc_cb = None
        self._class_name = TRAY_WINDOW_CLASS
        self._taskbar_msg = 0
        self._notify_lock = threading.Lock()
        self._notify_payload: tuple[str, str] | None = None

    # ------------------------------------------------------------- 对外接口
    def start(self) -> None:
        if not IS_WINDOWS:
            self.error = "仅支持 Windows"
            self.started.set()
            return
        self._thread = threading.Thread(
            target=self._run, name="blueprint-tray", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> bool:
        """请求结束托盘线程。返回 True 表示线程已确实退出。"""
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread is None:
            return True
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    def notify(self, title: str, text: str) -> None:
        """在弹出的气泡提示中显示一句话（失败静默忽略）。"""
        if not self.available or not self._hwnd:
            return
        with self._notify_lock:
            self._notify_payload = (title, text)
        user32.PostMessageW(self._hwnd, WM_TRAYNOTIFY, 0, 0)

    def tooltip_text(self) -> str:
        return self.tooltip

    # ------------------------------------------------------------- 线程主体
    def _run(self) -> None:
        try:
            self._create_window()
            self._add_icon()
            self._register_hotkey()
        except Exception as exc:  # noqa: BLE001 - 任何失败都不应影响主程序
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.started.set()

        if not self._hwnd:
            return
        try:
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret in (0, -1):
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"

    def _create_window(self) -> None:
        self._wndproc_cb = WNDPROC(self._wndproc)
        hinst = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc_cb
        wc.hInstance = hinst
        wc.lpszClassName = self._class_name
        if not user32.RegisterClassW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(err)

        hwnd = user32.CreateWindowExW(
            0, self._class_name, "BlueprintTray", 0, 0, 0, 0, 0,
            None, None, hinst, None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._hwnd = hwnd
        self._taskbar_msg = user32.RegisterWindowMessageW("TaskbarCreated")

    def _load_hicon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            cx = user32.GetSystemMetrics(SM_CXSMICON)
            cy = user32.GetSystemMetrics(SM_CYSMICON)
            handle = user32.LoadImageW(
                None, self.icon_path, IMAGE_ICON, cx, cy, LR_LOADFROMFILE
            )
            if handle:
                return handle
        return user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def _add_icon(self) -> None:
        self._hicon = self._load_hicon()
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = self.tooltip
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            raise ctypes.WinError(ctypes.get_last_error())
        self._nid = nid
        self.available = True

    def _remove_icon(self) -> None:
        if self._nid is not None:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._nid = None
        self.available = False

    def _register_hotkey(self) -> None:
        if not self.hotkey_enabled:
            return
        mods = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
        if user32.RegisterHotKey(self._hwnd, HOTKEY_ID, mods, VK_J):
            self.hotkey_ok = True
        else:
            self.hotkey_error = ctypes.get_last_error()
            self.hotkey_ok = False

    def _unregister_hotkey(self) -> None:
        if self.hotkey_ok and self._hwnd:
            user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
            self.hotkey_ok = False

    # ------------------------------------------------------------- 消息处理
    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAYICON:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.open_event.set()
                elif lparam == WM_RBUTTONUP:
                    self._show_menu(hwnd)
                return 0
            if msg == WM_HOTKEY:
                self.hotkey_event.set()
                return 0
            if msg == WM_ACTIVATE:
                self.activate_event.set()
                return 0
            if msg == WM_COMMAND:
                command = int(wparam) & 0xFFFF
                if command == IDM_OPEN:
                    self.open_event.set()
                elif command == IDM_HIDE:
                    self.hide_event.set()
                elif command == IDM_QUIT:
                    self.quit_event.set()
                return 0
            if msg == WM_TRAYNOTIFY:
                self._flush_notify()
                return 0
            if self._taskbar_msg and msg == self._taskbar_msg:
                try:
                    self._remove_icon()
                    self._add_icon()
                except Exception:  # noqa: BLE001
                    pass
                return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                self._remove_icon()
                self._unregister_hotkey()
                user32.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001 - 回调中绝不能抛异常
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self, hwnd) -> None:
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            user32.AppendMenuW(menu, MF_STRING, IDM_OPEN, "打开主界面")
            user32.AppendMenuW(menu, MF_STRING, IDM_HIDE, "最小化到托盘")
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, IDM_QUIT, "退出")

            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(hwnd)
            command = user32.TrackPopupMenu(
                menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                point.x, point.y, 0, hwnd, None,
            )
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)

        if command:
            user32.PostMessageW(hwnd, WM_COMMAND, command, 0)

    def _flush_notify(self) -> None:
        with self._notify_lock:
            payload = self._notify_payload
            self._notify_payload = None
        if payload is None or self._nid is None:
            return
        title, text = payload
        nid = self._nid
        previous = nid.uFlags
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        nid.dwInfoFlags = NIIF_INFO
        try:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        finally:
            nid.uFlags = previous
