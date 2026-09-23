"""蓝图 Blueprint 安装程序（多语言：English / 简体中文 / 繁體中文）。

- 默认界面语言为 English
- 自定安装路径
- 可选：创建桌面快捷方式 / 开机自动启动 / 安装完成后启动
- 附带卸载程序（安装目录下的 Uninstall.exe，亦可在「应用和功能」中卸载）

构建方式见 build_installer.py。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
import winreg
from tkinter import filedialog, ttk

APP_NAME = "Blueprint"
APP_NAME_CN = "蓝图 Blueprint"
APP_VERSION = "1.1.0"
PUBLISHER = "Blueprint"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Blueprint Blueprint"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "BlueprintBlueprint"
CONFIG_DIR_NAME = "Blueprint configuration file"

ACCENT = "#2f6bff"
ACCENT_HOVER = "#1f55e0"
BG = "#eef0f8"
PANEL = "#ffffff"
BORDER = "#dcdff0"
TEXT = "#2b3040"
MUTED = "#7a869a"

LANGUAGES = ("en", "zh_CN", "zh_TW")

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Blueprint Setup",
        "lang_title": "Choose setup language",
        "lang_sub": "Select the language used by the setup program.",
        "continue": "Continue",
        "options_title": "Installation options",
        "options_sub": "Choose where to install Blueprint and which extras to enable.",
        "install_dir": "Install location",
        "browse": "Browse...",
        "shortcut": "Create a desktop shortcut",
        "startup": "Start Blueprint automatically when Windows starts",
        "launch": "Launch Blueprint when setup finishes",
        "data_note": 'Your plans and settings are stored in the "Blueprint configuration file" folder.',
        "install": "Install",
        "back": "Back",
        "cancel": "Cancel",
        "installing": "Installing Blueprint...",
        "step_copy": "Copying program files...",
        "step_config": "Creating data folder...",
        "step_shortcut": "Creating shortcuts...",
        "step_startup": "Registering startup entry...",
        "step_uninstall": "Registering uninstaller...",
        "done_title": "Setup complete",
        "done_sub": "Blueprint has been installed successfully.",
        "finish": "Finish",
        "failed": "Setup failed",
        "need_dir": "Please choose an install location.",
        "exists_warn": "The folder already exists and will be used.",
        "uninstall_title": "Uninstall Blueprint",
        "uninstall_ask": "Remove Blueprint from your computer?",
        "uninstall_keep": 'Also delete my plans and settings (the "Blueprint configuration file" folder)',
        "uninstall_btn": "Uninstall",
        "uninstall_done": "Blueprint has been removed from your computer.",
        "close": "Close",
    },
    "zh_CN": {
        "title": "蓝图 Blueprint 安装程序",
        "lang_title": "选择安装语言",
        "lang_sub": "请选择安装程序使用的语言。",
        "continue": "继续",
        "options_title": "安装选项",
        "options_sub": "选择安装位置以及需要启用的附加选项。",
        "install_dir": "安装位置",
        "browse": "浏览...",
        "shortcut": "创建桌面快捷方式",
        "startup": "开机时自动启动蓝图 Blueprint",
        "launch": "安装完成后立即启动蓝图 Blueprint",
        "data_note": "计划与设置保存在「Blueprint configuration file」文件夹中。",
        "install": "安装",
        "back": "上一步",
        "cancel": "取消",
        "installing": "正在安装蓝图 Blueprint……",
        "step_copy": "正在复制程序文件……",
        "step_config": "正在创建数据文件夹……",
        "step_shortcut": "正在创建快捷方式……",
        "step_startup": "正在写入开机启动项……",
        "step_uninstall": "正在注册卸载程序……",
        "done_title": "安装完成",
        "done_sub": "蓝图 Blueprint 已成功安装。",
        "finish": "完成",
        "failed": "安装失败",
        "need_dir": "请选择安装位置。",
        "exists_warn": "该文件夹已存在，将被直接使用。",
        "uninstall_title": "卸载蓝图 Blueprint",
        "uninstall_ask": "确定要从这台电脑上移除蓝图 Blueprint 吗？",
        "uninstall_keep": "同时删除我的计划与设置（「Blueprint configuration file」文件夹）",
        "uninstall_btn": "卸载",
        "uninstall_done": "蓝图 Blueprint 已从这台电脑上移除。",
        "close": "关闭",
    },
    "zh_TW": {
        "title": "藍圖 Blueprint 安裝程式",
        "lang_title": "選擇安裝語言",
        "lang_sub": "請選擇安裝程式使用的語言。",
        "continue": "繼續",
        "options_title": "安裝選項",
        "options_sub": "選擇安裝位置以及要啟用的附加選項。",
        "install_dir": "安裝位置",
        "browse": "瀏覽...",
        "shortcut": "建立桌面捷徑",
        "startup": "開機時自動啟動藍圖 Blueprint",
        "launch": "安裝完成後立即啟動藍圖 Blueprint",
        "data_note": "計畫與設定儲存在「Blueprint configuration file」資料夾中。",
        "install": "安裝",
        "back": "上一步",
        "cancel": "取消",
        "installing": "正在安裝藍圖 Blueprint……",
        "step_copy": "正在複製程式檔案……",
        "step_config": "正在建立資料資料夾……",
        "step_shortcut": "正在建立捷徑……",
        "step_startup": "正在寫入開機啟動項……",
        "step_uninstall": "正在註冊卸載程式……",
        "done_title": "安裝完成",
        "done_sub": "藍圖 Blueprint 已成功安裝。",
        "finish": "完成",
        "failed": "安裝失敗",
        "need_dir": "請選擇安裝位置。",
        "exists_warn": "該資料夾已存在，將直接使用。",
        "uninstall_title": "卸載藍圖 Blueprint",
        "uninstall_ask": "確定要從這台電腦移除藍圖 Blueprint 嗎？",
        "uninstall_keep": "同時刪除我的計畫與設定（「Blueprint configuration file」資料夾）",
        "uninstall_btn": "卸載",
        "uninstall_done": "藍圖 Blueprint 已從這台電腦移除。",
        "close": "關閉",
    },
}

FONTS = {"en": "Segoe UI", "zh_CN": "Microsoft YaHei UI", "zh_TW": "Microsoft JhengHei UI"}


# ====================================================================== 工具
def setup_dir() -> str:
    """当前安装程序（exe）所在位置。"""
    return os.path.dirname(os.path.abspath(sys.executable))


def payload_dir() -> str:
    """内置的程序文件目录（打包后位于临时解包目录）。"""
    base = getattr(sys, "_MEIPASS", None) or setup_dir()
    return os.path.join(base, "payload")


def default_install_dir() -> str:
    """默认安装位置：优先使用非系统盘。"""
    for drive in ("D:", "E:", "F:"):
        root = drive + "\\"
        if os.path.exists(root):
            return os.path.join(root, "APP", "Blueprint Blueprint")
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", "Blueprint Blueprint")


def ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def run_powershell(script: str) -> bool:
    """执行一段 PowerShell 脚本（写入 UTF-8 BOM 临时文件，避免中文乱码）。"""
    handle, path = tempfile.mkstemp(suffix=".ps1")
    os.close(handle)
    try:
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write(script)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for shell in ("powershell.exe", "pwsh.exe"):
            try:
                result = subprocess.run(
                    [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
                    capture_output=True, creationflags=flags,
                )
            except FileNotFoundError:
                continue
            if result.returncode == 0:
                return True
        return False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def create_shortcut(lnk: str, target: str, arguments: str = "",
                    workdir: str = "", icon: str = "", description: str = "") -> bool:
    script = f"""$ErrorActionPreference = "Stop"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut({ps_quote(lnk)})
$shortcut.TargetPath = {ps_quote(target)}
$shortcut.Arguments = {ps_quote(arguments)}
$shortcut.WorkingDirectory = {ps_quote(workdir)}
$shortcut.IconLocation = {ps_quote(icon)}
$shortcut.Description = {ps_quote(description)}
$shortcut.WindowStyle = 1
$shortcut.Save()
"""
    return run_powershell(script)


def desktop_dir() -> str:
    path = os.path.join(os.path.expanduser("~"), "Desktop")
    for candidate in (os.environ.get("USERPROFILE", "") + "\\Desktop",):
        if os.path.isdir(candidate):
            path = candidate
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
        if buf.value:
            path = buf.value
    except Exception:
        pass
    return path


def start_menu_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")


def set_startup(enabled: bool, command: str = "") -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def remove_startup() -> None:
    set_startup(False)


def dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


# ====================================================================== 主界面
class SetupWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.lang = "en"
        self.installed_dir = ""
        self.page = ""
        self._progress_var = tk.DoubleVar(value=0)

        self.withdraw()
        self.title(APP_NAME + " Setup")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._set_icon()

        self.outer = tk.Frame(self, bg=BG)
        self.outer.pack(fill="both", expand=True)
        self._build_language_page()
        self._place()

    # ------------------------------------------------------------ 基础
    def t(self, key: str) -> str:
        table = STRINGS.get(self.lang) or STRINGS["en"]
        return table.get(key, STRINGS["en"].get(key, key))

    def font(self, size: int = 10, bold: bool = False) -> tuple:
        family = FONTS.get(self.lang, "Segoe UI")
        return (family, size, "bold") if bold else (family, size)

    def _set_icon(self) -> None:
        icon = os.path.join(getattr(sys, "_MEIPASS", "") or "", "blueprint.ico")
        if not os.path.exists(icon):
            icon = os.path.join(setup_dir(), "blueprint.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

    def _place(self) -> None:
        self.update_idletasks()
        width = max(620, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2 - 100)
        y = max(0, (screen_h - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()

    def _clear(self) -> None:
        for child in self.outer.winfo_children():
            child.destroy()

    def _card(self) -> tk.Frame:
        self._clear()
        wrapper = tk.Frame(self.outer, bg=BG, padx=22, pady=20)
        wrapper.pack(fill="both", expand=True)
        card = tk.Frame(wrapper, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="both", expand=True)
        return card

    def _heading(self, parent: tk.Frame, title_key: str, sub_key: str) -> None:
        head = tk.Frame(parent, bg=PANEL)
        head.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(head, text=self.t(title_key), bg=PANEL, fg=TEXT,
                 font=self.font(15, bold=True)).pack(anchor="w")
        tk.Label(head, text=self.t(sub_key), bg=PANEL, fg=MUTED,
                 font=self.font(10)).pack(anchor="w", pady=(6, 0))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=24, pady=(16, 0))

    def _button(self, parent, text, command, accent=False, width=12):
        return tk.Button(
            parent, text=text, command=command, bd=0, relief="flat",
            cursor="hand2", font=self.font(10), width=width, padx=10, pady=7,
            bg=ACCENT if accent else "#e7ecf7",
            fg="#ffffff" if accent else TEXT,
            activebackground=ACCENT_HOVER if accent else "#d6deee",
            activeforeground="#ffffff" if accent else TEXT,
        )

    # ------------------------------------------------------------ 页 1
    def _build_language_page(self) -> None:
        self.page = "language"
        self.title(self.t("title"))
        card = self._card()
        self._heading(card, "lang_title", "lang_sub")

        body = tk.Frame(card, bg=PANEL)
        body.pack(fill="x", padx=24, pady=20)
        self.lang_var = tk.StringVar(value="en")
        labels = (("en", "English"), ("zh_CN", "简体中文"), ("zh_TW", "繁體中文"))
        for code, label in labels:
            row = tk.Frame(body, bg=PANEL)
            row.pack(fill="x", pady=4)
            tk.Radiobutton(
                row, text=label, variable=self.lang_var, value=code,
                bg=PANEL, fg=TEXT, activebackground=PANEL, selectcolor=PANEL,
                font=self.font(11), bd=0, highlightthickness=0, anchor="w",
                cursor="hand2",
            ).pack(side="left")

        footer = tk.Frame(card, bg=PANEL)
        footer.pack(fill="x", padx=24, pady=(0, 20))
        self._button(footer, self.t("continue"), self._on_continue,
                     accent=True).pack(side="right")
        self._button(footer, self.t("cancel"), self.destroy).pack(
            side="right", padx=(0, 8))

    def _on_continue(self) -> None:
        self.lang = self.lang_var.get()
        if self.lang not in LANGUAGES:
            self.lang = "en"
        self._build_options_page()

    # ------------------------------------------------------------ 页 2
    def _build_options_page(self) -> None:
        self.page = "options"
        self.title(self.t("title"))
        card = self._card()
        self._heading(card, "options_title", "options_sub")

        body = tk.Frame(card, bg=PANEL)
        body.pack(fill="x", padx=24, pady=(18, 0))

        tk.Label(body, text=self.t("install_dir"), bg=PANEL, fg=TEXT,
                 font=self.font(10, bold=True)).pack(anchor="w")
        path_row = tk.Frame(body, bg=PANEL)
        path_row.pack(fill="x", pady=(6, 0))
        self.dir_var = tk.StringVar(value=default_install_dir())
        entry = tk.Entry(path_row, textvariable=self.dir_var, font=self.font(10),
                         bd=1, relief="solid", bg="#ffffff", fg=TEXT,
                         highlightthickness=0, insertbackground=TEXT)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        self._button(path_row, self.t("browse"), self._browse, width=9).pack(
            side="left", padx=(8, 0))

        self.shortcut_var = tk.BooleanVar(value=True)
        self.startup_var = tk.BooleanVar(value=False)
        self.launch_var = tk.BooleanVar(value=True)
        for var, key in (
            (self.shortcut_var, "shortcut"),
            (self.startup_var, "startup"),
            (self.launch_var, "launch"),
        ):
            tk.Checkbutton(
                body, text=self.t(key), variable=var, bg=PANEL, fg=TEXT,
                activebackground=PANEL, selectcolor=PANEL, font=self.font(10),
                bd=0, highlightthickness=0, anchor="w", cursor="hand2",
            ).pack(anchor="w", pady=(10, 0))

        tk.Label(body, text=self.t("data_note"), bg=PANEL, fg=MUTED,
                 font=self.font(9), justify="left", wraplength=520).pack(
            anchor="w", pady=(14, 0))

        footer = tk.Frame(card, bg=PANEL)
        footer.pack(fill="x", padx=24, pady=20)
        self._button(footer, self.t("install"), self._on_install,
                     accent=True).pack(side="right")
        self._button(footer, self.t("back"), self._build_language_page).pack(
            side="right", padx=(0, 8))

    def _browse(self) -> None:
        current = self.dir_var.get().strip()
        initial = current if os.path.isdir(current) else None
        chosen = filedialog.askdirectory(
            title=self.t("install_dir"), initialdir=initial, mustexist=False)
        if chosen:
            self.dir_var.set(os.path.normpath(chosen))

    # ------------------------------------------------------------ 页 3
    def _build_progress_page(self) -> None:
        self.page = "progress"
        card = self._card()
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(head, text=self.t("installing"), bg=PANEL, fg=TEXT,
                 font=self.font(13, bold=True)).pack(anchor="w")

        self.log = tk.Text(card, height=8, bd=0, relief="flat", bg="#f7f8fe",
                           fg=TEXT, font=self.font(10), padx=12, pady=10,
                           highlightthickness=1, highlightbackground=BORDER,
                           wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=24, pady=16)

        self.progress = ttk.Progressbar(card, variable=self._progress_var,
                                        maximum=100, length=560)
        self.progress.pack(fill="x", padx=24)

        footer = tk.Frame(card, bg=PANEL)
        footer.pack(fill="x", padx=24, pady=20)
        self.finish_btn = self._button(footer, self.t("finish"), self._on_finish,
                                       accent=True)
        self.finish_btn.configure(state="disabled")
        self.finish_btn.pack(side="right")

    def _log(self, message: str, progress: float | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        if progress is not None:
            self._progress_var.set(progress)
        self.update()

    def _on_install(self) -> None:
        target = self.dir_var.get().strip().strip('"')
        if not target:
            self._error(self.t("need_dir"))
            return
        self._build_progress_page()
        self.update()
        try:
            self._run_install(os.path.normpath(target))
        except Exception as exc:  # noqa: BLE001 - 安装失败需给出提示
            self._log(f"{self.t('failed')}: {exc}")
            self.finish_btn.configure(state="normal")
            return
        self._show_done()

    def _run_install(self, target: str) -> None:
        steps = [
            (self.t("step_copy"), 20, lambda: self._copy_payload(target)),
            (self.t("step_config"), 45, lambda: self._make_config_dir(target)),
            (self.t("step_shortcut"), 65, lambda: self._make_shortcuts(target)),
            (self.t("step_startup"), 80, lambda: self._apply_startup(target)),
            (self.t("step_uninstall"), 100, lambda: self._register_uninstall(target)),
        ]
        for message, progress, action in steps:
            self._log(message, progress)
            action()
        self.installed_dir = target

    def _copy_payload(self, target: str) -> None:
        source = payload_dir()
        os.makedirs(target, exist_ok=True)
        if os.path.isdir(source):
            for name in os.listdir(source):
                src = os.path.join(source, name)
                dst = os.path.join(target, name)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

    def _make_config_dir(self, target: str) -> None:
        os.makedirs(os.path.join(target, CONFIG_DIR_NAME), exist_ok=True)

    def _make_shortcuts(self, target: str) -> None:
        exe = os.path.join(target, "Blueprint.exe")
        icon = os.path.join(target, "blueprint.ico")
        if self.shortcut_var.get():
            create_shortcut(
                os.path.join(desktop_dir(), "Blueprint Blueprint.lnk"),
                exe, "", target, icon, "Blueprint Blueprint - Plans & Records",
            )
        create_shortcut(
            os.path.join(start_menu_dir(), "Blueprint Blueprint.lnk"),
            exe, "", target, icon, "Blueprint Blueprint - Plans & Records",
        )

    def _apply_startup(self, target: str) -> None:
        exe = os.path.join(target, "Blueprint.exe")
        set_startup(bool(self.startup_var.get()), f'"{exe}" --tray')

    def _register_uninstall(self, target: str) -> None:
        try:
            shutil.copy2(os.path.abspath(sys.executable),
                         os.path.join(target, "Uninstall.exe"))
        except OSError:
            pass

        exe = os.path.join(target, "Blueprint.exe")
        uninstall = os.path.join(target, "Uninstall.exe")
        size_kb = max(1, dir_size(target) // 1024)
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ,
                                  "Blueprint Blueprint")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, target)
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe)
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                                  f'"{uninstall}" --uninstall')
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        except OSError:
            pass

    def _show_done(self) -> None:
        self.page = "done"
        self._clear()
        wrapper = tk.Frame(self.outer, bg=BG, padx=22, pady=20)
        wrapper.pack(fill="both", expand=True)
        card = tk.Frame(wrapper, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="both", expand=True)
        self._heading(card, "done_title", "done_sub")

        body = tk.Frame(card, bg=PANEL)
        body.pack(fill="x", padx=24, pady=18)
        tk.Label(body, text=f"{self.t('install_dir')}: {self.installed_dir}",
                 bg=PANEL, fg=MUTED, font=self.font(9), justify="left",
                 wraplength=540).pack(anchor="w")
        tk.Label(body, text=self.t("data_note"), bg=PANEL, fg=MUTED,
                 font=self.font(9), justify="left", wraplength=540).pack(
            anchor="w", pady=(6, 0))

        footer = tk.Frame(card, bg=PANEL)
        footer.pack(fill="x", padx=24, pady=20)
        self._button(footer, self.t("finish"), self._on_finish,
                     accent=True).pack(side="right")
        if self.launch_var.get():
            self.after(200, self._launch_app)

    def _launch_app(self) -> None:
        exe = os.path.join(self.installed_dir, "Blueprint.exe")
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe], cwd=self.installed_dir)
            except OSError:
                pass

    def _on_finish(self) -> None:
        self.destroy()

    def _error(self, message: str) -> None:
        from tkinter import messagebox
        messagebox.showerror(self.t("title"), message, parent=self)


# ====================================================================== 卸载
class UninstallWindow(tk.Tk):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = target
        self.lang = "en"
        self._detect_lang()

        self.title(self.t("uninstall_title"))
        self.resizable(False, False)
        self.configure(bg=BG)
        icon = os.path.join(target, "blueprint.ico")
        if os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

        card = tk.Frame(self, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER, padx=24, pady=20)
        card.pack(fill="both", expand=True, padx=22, pady=20)
        tk.Label(card, text=self.t("uninstall_title"), bg=PANEL, fg=TEXT,
                 font=self.font(13, bold=True)).pack(anchor="w")
        tk.Label(card, text=self.t("uninstall_ask"), bg=PANEL, fg=MUTED,
                 font=self.font(10), justify="left", wraplength=420).pack(
            anchor="w", pady=(8, 0))

        self.keep_var = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text=self.t("uninstall_keep"), variable=self.keep_var,
                       bg=PANEL, fg=TEXT, activebackground=PANEL, selectcolor=PANEL,
                       font=self.font(9), bd=0, highlightthickness=0,
                       anchor="w", justify="left", wraplength=420,
                       cursor="hand2").pack(anchor="w", pady=(14, 0))

        footer = tk.Frame(card, bg=PANEL)
        footer.pack(fill="x", pady=(20, 0))
        self._button(footer, self.t("uninstall_btn"), self._do_uninstall,
                     accent=True).pack(side="right")
        self._button(footer, self.t("cancel"), self.destroy).pack(
            side="right", padx=(0, 8))

        self.update_idletasks()
        self.geometry(f"+{max(0,(self.winfo_screenwidth()-self.winfo_reqwidth())//2-100)}"
                      f"+{max(0,(self.winfo_screenheight()-self.winfo_reqheight())//3)}")

    def _detect_lang(self) -> None:
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary = lang_id & 0x3FF
            if primary == 0x04:
                self.lang = "zh_CN"
            elif primary == 0x0404 or (lang_id & 0x3FF) == 0x04 and (lang_id >> 10) == 1:
                self.lang = "zh_TW"
        except Exception:
            self.lang = "en"

    def t(self, key: str) -> str:
        table = STRINGS.get(self.lang) or STRINGS["en"]
        return table.get(key, STRINGS["en"].get(key, key))

    def font(self, size: int = 10, bold: bool = False) -> tuple:
        family = FONTS.get(self.lang, "Segoe UI")
        return (family, size, "bold") if bold else (family, size)

    def _button(self, parent, text, command, accent=False, width=12):
        return tk.Button(
            parent, text=text, command=command, bd=0, relief="flat",
            cursor="hand2", font=self.font(10), width=width, padx=10, pady=7,
            bg=ACCENT if accent else "#e7ecf7",
            fg="#ffffff" if accent else TEXT,
            activebackground=ACCENT_HOVER if accent else "#d6deee",
            activeforeground="#ffffff" if accent else TEXT,
        )

    def _do_uninstall(self) -> None:
        target = self.target
        remove_data = bool(self.keep_var.get())

        for lnk in (
            os.path.join(desktop_dir(), "Blueprint Blueprint.lnk"),
            os.path.join(start_menu_dir(), "Blueprint Blueprint.lnk"),
        ):
            try:
                os.remove(lnk)
            except OSError:
                pass

        remove_startup()

        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        except OSError:
            pass

        config_dir = os.path.join(target, CONFIG_DIR_NAME)
        uninstall_exe = os.path.join(target, "Uninstall.exe")
        keep = os.path.normcase(config_dir)

        # 立即删除程序文件（正在运行的 Uninstall.exe 除外，稍后延迟删除）
        try:
            entries = os.listdir(target)
        except OSError:
            entries = []
        for name in entries:
            path = os.path.join(target, name)
            if os.path.normcase(path) == os.path.normcase(uninstall_exe):
                continue
            if os.path.normcase(path) == keep and not remove_data:
                continue
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass

        self.destroy()

        # 自身无法删除正在运行的文件，交给一个延迟的 shell 完成
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        script = (
            f'timeout /t 2 /nobreak >nul & '
            f'del /f /q "{uninstall_exe}" >nul 2>&1 & '
            f'rd /s /q "{target}" >nul 2>&1'
        )
        try:
            subprocess.Popen(["cmd", "/c", script], creationflags=flags)
        except OSError:
            pass


def main() -> int:
    target = ""
    for index, arg in enumerate(sys.argv):
        if arg == "--uninstall" and index + 1 < len(sys.argv):
            target = sys.argv[index + 1]
    if "--uninstall" in sys.argv:
        if not target:
            target = os.path.dirname(os.path.abspath(sys.executable))
        UninstallWindow(target).mainloop()
        return 0

    SetupWindow().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
