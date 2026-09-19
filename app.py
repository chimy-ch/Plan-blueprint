"""蓝图 Blueprint —— 以「计划」为核心的桌面计划与记录应用。

主界面：
  · 顶栏：左上角「设置」，右侧主题快速切换
  · 计划管理：筛选 / 搜索 / 排序 + 计划列表 + 详情(子任务 / 进度记录)
  · 数据统计：总览卡片 + 分类统计 + 最近记录

界面支持浅色 / 深色两套主题与多种主题色，均可在「设置」中调整。
数据库、设置、日志等文件统一保存在「Blueprint configuration file」目录（见 paths.py）。
"""

from __future__ import annotations

import os
import time
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

import db
import paths
import single_instance
import startup
import tray as tray_mod
import winicon
from theme import ACCENTS, FONT_SIZES, THEME_LABELS, Settings, build_palette
from widgets import CalendarDateEntry

APP_NAME = "蓝图 Blueprint"
APP_SUBTITLE = "计划与记录"
HERE = paths.APP_DIR
ICON_PATH = paths.ICON_PATH
ICONS_DIR = paths.ICONS_DIR
FONT = "Microsoft YaHei UI"

PLAN_COLUMNS = (
    ("title", "计划", 180, "w"),
    ("category", "分类", 64, "center"),
    ("priority", "优先级", 58, "center"),
    ("status", "状态", 68, "center"),
    ("due", "截止日期", 92, "center"),
    ("progress", "进度", 58, "center"),
)

FILTER_STATUS = ("全部", "未开始", "进行中", "已完成", "已搁置", "今日到期", "逾期")


class PlanFlowApp:
    # ==================================================================
    # 启动
    # ==================================================================
    def __init__(self, root: tk.Tk, start_hidden: bool = False) -> None:
        self.root = root
        self.db = db.Database()
        self.settings = Settings()
        self.current_plan_id: int | None = None
        self.status_var = tk.StringVar(value="就绪")
        self.dialog: "SettingsDialog | None" = None
        self._images: dict[str, tk.PhotoImage] = {}
        self.hidden = False
        self.tray: tray_mod.TrayService | None = None
        self._quitting = False
        self._tray_reported = False
        self._tray_tip_shown = False
        self._poll_job: str | None = None
        self._hotkey_state = bool(self.settings.get("hotkey_enabled"))

        self.font_size = int(self.settings.get("font_size", 10))
        self.colors = build_palette(self.settings.get("theme"), self.settings.get("accent"))

        self._configure_root()
        self._build_style()
        self._load_images()
        self._set_icon()

        self.container = tk.Frame(root, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True)
        self._build_layout()

        self._bind_shortcuts()
        self.refresh_all()
        self._init_tray()
        if start_hidden:
            self.root.after(500, lambda: self.hide_to_tray(notify=False))

    def _configure_root(self) -> None:
        c = self.colors
        self.root.title(f"{APP_NAME} · {APP_SUBTITLE}")
        self.root.minsize(1000, 640)
        self.root.configure(bg=c["bg"])
        geometry = str(self.settings.get("geometry") or "")
        if self.settings.get("remember_geometry") and geometry:
            try:
                self.root.geometry(geometry)
                return
            except tk.TclError:
                pass
        self.root.geometry("1400x840")

    def _set_icon(self) -> None:
        if not os.path.exists(ICON_PATH):
            return
        try:
            self.root.iconbitmap(ICON_PATH)
            self.root.iconbitmap(default=ICON_PATH)
        except tk.TclError:
            pass
        winicon.register_app_id(paths.icon_uri(), APP_NAME)
        winicon.apply_window_icon(self.root, ICON_PATH)

    def _load_images(self) -> None:
        for name in ("gear_light", "gear_dark", "moon_light", "sun_dark", "logo"):
            if name in self._images:
                continue
            path = os.path.join(ICONS_DIR, f"{name}.png")
            if not os.path.exists(path):
                continue
            try:
                self._images[name] = tk.PhotoImage(file=path)
            except tk.TclError:
                pass

    def _icon(self, name: str) -> tk.PhotoImage | None:
        return self._images.get(name)

    # ==================================================================
    # 主题
    # ==================================================================
    def f(self, size: int | None = None, bold: bool = False) -> tuple:
        value = self.font_size if size is None else size
        return (FONT, value, "bold") if bold else (FONT, value)

    def is_dark(self) -> bool:
        return self.colors.get("mode") == "dark"

    def _build_style(self) -> None:
        c = self.colors
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=self.f(), background=c["bg"], foreground=c["text"])
        style.configure("TFrame", background=c["bg"])
        style.configure("Card.TFrame", background=c["panel"])

        style.configure("TLabel", background=c["bg"], foreground=c["text"])
        style.configure("Card.TLabel", background=c["panel"], foreground=c["text"])
        style.configure("Muted.TLabel", background=c["panel"], foreground=c["muted"])

        style.configure(
            "TButton", padding=(12, 6), background=c["btn_bg"], foreground=c["btn_fg"],
            borderwidth=0, focusthickness=0, relief="flat",
        )
        style.map(
            "TButton",
            background=[("disabled", c["btn_disabled"]), ("pressed", c["btn_hover"]),
                        ("active", c["btn_hover"])],
            foreground=[("disabled", c["btn_disabled_fg"])],
        )
        style.configure(
            "Accent.TButton", padding=(14, 6), background=c["accent"],
            foreground=c["accent_fg"], borderwidth=0, relief="flat",
        )
        style.map(
            "Accent.TButton",
            background=[("disabled", c["accent_dim"]), ("pressed", c["accent_press"]),
                        ("active", c["accent_hover"])],
            foreground=[("disabled", c["muted"])],
        )
        style.configure(
            "Ghost.TButton", padding=(10, 6), background=c["panel"],
            foreground=c["muted"], borderwidth=0, relief="flat",
        )
        style.map(
            "Ghost.TButton",
            background=[("active", c["btn_hover"]), ("pressed", c["btn_hover"])],
            foreground=[("active", c["text"])],
        )

        style.configure(
            "TEntry", fieldbackground=c["entry_bg"], foreground=c["text"],
            background=c["entry_bg"], bordercolor=c["entry_border"],
            lightcolor=c["entry_border"], darkcolor=c["entry_border"],
            insertcolor=c["text"], padding=5, relief="flat",
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", c["bg"])],
            foreground=[("disabled", c["muted"])],
        )

        style.configure(
            "TCombobox", fieldbackground=c["entry_bg"], background=c["btn_bg"],
            foreground=c["text"], bordercolor=c["entry_border"],
            lightcolor=c["entry_border"], darkcolor=c["entry_border"],
            arrowcolor=c["muted"], padding=4, relief="flat",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", c["entry_bg"]), ("disabled", c["bg"])],
            foreground=[("readonly", c["text"]), ("disabled", c["muted"])],
            background=[("readonly", c["btn_bg"]), ("active", c["btn_hover"])],
            arrowcolor=[("active", c["accent"])],
        )
        self.root.option_add("*TCombobox*Listbox.background", c["panel"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["accent_fg"])
        self.root.option_add("*TCombobox*Listbox.font", self.f())

        style.configure(
            "Treeview", background=c["panel"], fieldbackground=c["panel"],
            foreground=c["text"], rowheight=self.font_size + 18, borderwidth=0,
            relief="flat", font=self.f(),
        )
        style.configure(
            "Treeview.Heading", background=c["heading_bg"], foreground=c["heading_fg"],
            font=self.f(bold=True), relief="flat", padding=(6, 7), borderwidth=0,
        )
        style.map("Treeview.Heading", background=[("active", c["border"])])
        style.map(
            "Treeview",
            background=[("selected", c["accent"])],
            foreground=[("selected", c["accent_fg"])],
        )

        style.configure(
            "Vertical.TScrollbar", background=c["panel_alt"], troughcolor=c["bg"],
            bordercolor=c["bg"], arrowcolor=c["muted"], lightcolor=c["panel_alt"],
            darkcolor=c["panel_alt"], relief="flat",
        )
        style.map("Vertical.TScrollbar", background=[("active", c["border"])])
        style.configure(
            "Horizontal.TScrollbar", background=c["panel_alt"], troughcolor=c["bg"],
            bordercolor=c["bg"], arrowcolor=c["muted"], lightcolor=c["panel_alt"],
            darkcolor=c["panel_alt"], relief="flat",
        )

        style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 6, 0, 0))
        style.configure(
            "TNotebook.Tab", padding=(20, 9), background=c["tab_bg"],
            foreground=c["tab_fg"], font=self.f(), borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", c["accent"]), ("active", c["tab_hover"])],
            foreground=[("selected", c["accent_fg"])],
        )

        style.configure("Detail.TNotebook", background=c["panel"], borderwidth=0,
                        tabmargins=(0, 4, 0, 0))
        style.configure(
            "Detail.TNotebook.Tab", padding=(14, 7), background=c["panel_alt"],
            foreground=c["muted"], font=self.f(), borderwidth=0,
        )
        style.map(
            "Detail.TNotebook.Tab",
            background=[("selected", c["accent_soft"]), ("active", c["btn_hover"])],
            foreground=[("selected", c["accent"])],
        )

        style.configure("TLabelframe", background=c["panel"], bordercolor=c["border"],
                        borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=c["panel"], foreground=c["text"],
                        font=self.f(bold=True))

        style.configure(
            "Horizontal.TProgressbar", background=c["accent"], troughcolor=c["trough"],
            bordercolor=c["trough"], lightcolor=c["accent"], darkcolor=c["accent"],
            borderwidth=0, thickness=16,
        )

        style.configure(
            "TCheckbutton", background=c["panel"], foreground=c["text"],
            focuscolor=c["panel"], indicatorcolor=c["entry_bg"],
            bordercolor=c["entry_border"], lightcolor=c["panel"], darkcolor=c["panel"],
            font=self.f(), padding=(0, 4),
        )
        style.map(
            "TCheckbutton",
            indicatorcolor=[("selected", c["accent"]), ("!selected", c["entry_bg"])],
            background=[("active", c["panel"])],
            foreground=[("disabled", c["muted"])],
        )

        style.configure(
            "TRadiobutton", background=c["panel"], foreground=c["text"],
            focuscolor=c["panel"], indicatorcolor=c["entry_bg"],
            lightcolor=c["panel"], darkcolor=c["panel"], font=self.f(),
        )
        style.map(
            "TRadiobutton",
            indicatorcolor=[("selected", c["accent"]), ("!selected", c["entry_bg"])],
            background=[("active", c["panel"])],
        )

        style.configure(
            "Horizontal.TScale", background=c["accent"], troughcolor=c["trough"],
            bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"],
        )
        style.map(
            "Horizontal.TScale",
            background=[("active", c["accent_hover"])],
            lightcolor=[("active", c["accent_hover"])],
            darkcolor=[("active", c["accent_hover"])],
        )

        style.configure("TSeparator", background=c["border"])
        style.configure("TPanedwindow", background=c["bg"], sashthickness=8)

    def toggle_theme(self) -> None:
        new_mode = "light" if self.is_dark() else "dark"
        self.settings.set("theme", new_mode)
        self.settings.save()
        self.apply_settings()
        self.set_status("已切换到浅色主题" if new_mode == "light" else "已切换到深色主题")

    def apply_settings(self) -> None:
        """重新生成调色板并就地重建界面（保留当前选中与筛选状态）。"""
        state = self._capture_state()
        self.font_size = int(self.settings.get("font_size", 10))
        self.colors = build_palette(self.settings.get("theme"), self.settings.get("accent"))
        self.root.configure(bg=self.colors["bg"])

        self._build_style()
        self._load_images()
        self._rebuild()
        self._restore_state(state)
        self.refresh_all()
        if self.current_plan_id is not None and self.db.get_plan(self.current_plan_id):
            self.load_plan(self.current_plan_id)

        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.rebuild()

        if bool(self.settings.get("hotkey_enabled")) != self._hotkey_state:
            self._hotkey_state = bool(self.settings.get("hotkey_enabled"))
            self._restart_tray()

    def _capture_state(self) -> dict:
        state: dict = {
            "tab": 0,
            "detail_tab": 0,
            "plan_id": self.current_plan_id,
            "search": "",
            "status": "全部",
            "category": "全部",
            "sort": self.settings.get("default_order"),
        }
        try:
            state["tab"] = max(0, self.nb.index(self.nb.select()))
        except (tk.TclError, AttributeError):
            pass
        try:
            state["detail_tab"] = max(0, self.detail_nb.index(self.detail_nb.select()))
        except (tk.TclError, AttributeError):
            pass
        for key, attr in (("search", "search_var"), ("status", "filter_status"),
                          ("category", "filter_category"), ("sort", "sort_var")):
            var = getattr(self, attr, None)
            if var is not None:
                state[key] = var.get()
        return state

    def _restore_state(self, state: dict) -> None:
        self.current_plan_id = state.get("plan_id")
        for key, attr in (("search", "search_var"), ("status", "filter_status"),
                          ("category", "filter_category"), ("sort", "sort_var")):
            var = getattr(self, attr, None)
            if var is not None and state.get(key) is not None:
                var.set(state[key])
        try:
            self.nb.select(state.get("tab", 0))
        except tk.TclError:
            pass
        try:
            self.detail_nb.select(state.get("detail_tab", 0))
        except tk.TclError:
            pass

    def _rebuild(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()
        self.container.configure(bg=self.colors["bg"])
        self._build_layout()

    # ==================================================================
    # 界面骨架
    # ==================================================================
    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda _e: self.new_plan())
        self.root.bind("<Control-s>", lambda _e: self.save_plan())
        self.root.bind("<F5>", lambda _e: self.refresh_all())
        self.root.bind("<Control-comma>", lambda _e: self.open_settings())
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        if self.settings.get("close_to_tray", False) and not self._quitting:
            self.hide_to_tray()
            self.set_status("已最小化到托盘继续运行 · 托盘图标右键可退出")
            return
        self._quitting = True
        if self.settings.get("remember_geometry"):
            try:
                self.settings.set("geometry", self.root.geometry())
            except tk.TclError:
                pass
        self.settings.save()
        self.db.close()
        self._stop_tray()
        self.root.destroy()

    # ==================================================================
    # 系统托盘与全局热键
    # ==================================================================
    def _init_tray(self) -> None:
        self.tray = tray_mod.TrayService(
            ICON_PATH,
            f"{APP_NAME} · {APP_SUBTITLE}",
            hotkey_enabled=bool(self.settings.get("hotkey_enabled")),
        )
        self.tray.start()
        self._schedule_poll()

    def _schedule_poll(self) -> None:
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except (tk.TclError, ValueError):
                pass
        self._poll_job = self.root.after(60, self._poll_tray)

    def _poll_tray(self) -> None:
        service = self.tray
        if service is not None:
            if service.hotkey_event.is_set():
                service.hotkey_event.clear()
                self.toggle_window()
            if service.open_event.is_set():
                service.open_event.clear()
                self.show_window()
            if service.activate_event.is_set():
                service.activate_event.clear()
                self.show_window()
            if service.hide_event.is_set():
                service.hide_event.clear()
                self.hide_to_tray()
            if service.quit_event.is_set():
                service.quit_event.clear()
                self.request_quit()
            if service.started.is_set() and not self._tray_reported:
                self._report_tray()
        self._schedule_poll()

    def _report_tray(self) -> None:
        self._tray_reported = True
        service = self.tray
        if service is None:
            return
        if service.error:
            self.set_status(f"托盘 / 热键启动失败：{service.error}")
            return
        problems = []
        if not service.available:
            problems.append("系统托盘图标不可用")
        if bool(self.settings.get("hotkey_enabled")) and not service.hotkey_ok:
            problems.append(f"全局热键 {tray_mod.HOTKEY_LABEL} 已被其他程序占用")
        if problems:
            self.set_status("提示：" + "；".join(problems))

    def _restart_tray(self) -> None:
        if self.tray is not None:
            if not self.tray.stop():
                deadline = time.monotonic() + 1.5
                while time.monotonic() < deadline and tray_mod.tray_window_exists():
                    time.sleep(0.05)
            self.tray = None
        self._tray_reported = False
        self._init_tray()

    def _stop_tray(self) -> None:
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except (tk.TclError, ValueError):
                pass
            self._poll_job = None
        if self.tray is not None:
            self.tray.stop()
            self.tray = None

    def hide_to_tray(self, notify: bool = True) -> None:
        """把窗口收起到系统托盘。"""
        if self.hidden:
            return
        self.hidden = True
        try:
            self.root.withdraw()
        except tk.TclError:
            self.hidden = False
            return
        self.set_status(f"已最小化到托盘 · 按 {tray_mod.HOTKEY_LABEL} 呼出")
        service = self.tray
        if notify and service is not None and not self._tray_tip_shown:
            self._tray_tip_shown = True
            service.notify(APP_NAME,
                           f"已最小化到系统托盘，按 {tray_mod.HOTKEY_LABEL} 可随时呼出。")

    def show_window(self) -> None:
        """从托盘恢复并置前。"""
        self.hidden = False
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(150, self._drop_topmost)
            self.root.focus_force()
        except tk.TclError:
            pass
        self.set_status("已从托盘恢复")

    def _drop_topmost(self) -> None:
        try:
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass

    def toggle_window(self) -> None:
        """全局热键行为：已收起则呼出；正在前台使用则收起；否则置前。"""
        if self.hidden:
            self.show_window()
        elif self.is_foreground():
            self.hide_to_tray()
        else:
            self.show_window()

    def is_foreground(self) -> bool:
        hwnd = tray_mod.foreground_window()
        if not hwnd:
            return False
        return tray_mod.window_process_id(hwnd) == os.getpid()

    def _on_unmap(self, _event=None) -> None:
        if self.hidden or self._quitting:
            return
        if not self.settings.get("minimize_to_tray", True):
            return
        try:
            if self.root.state() == "iconic":
                self.hide_to_tray()
        except tk.TclError:
            pass

    def request_quit(self) -> None:
        self._quitting = True
        self.on_close()

    def card(self, parent: tk.Misc, **kwargs) -> tk.Frame:
        c = self.colors
        return tk.Frame(parent, bg=c["panel"], highlightthickness=1,
                        highlightbackground=c["border"], highlightcolor=c["border"],
                        bd=0, **kwargs)

    def label(self, parent: tk.Misc, text: str = "", tone: str = "text",
              size: int | None = None, bold: bool = False, bg_role: str = "panel",
              **kwargs) -> tk.Label:
        return tk.Label(parent, text=text, bg=self.colors[bg_role],
                        fg=self.colors[tone], font=self.f(size, bold), **kwargs)

    def _flat_button(self, parent: tk.Misc, text: str = "", image=None, command=None,
                     padx: int = 12, pady: int = 7, bg_role: str = "topbar",
                     tone: str = "text", font=None, compound: str = "left") -> tk.Button:
        c = self.colors
        button = tk.Button(
            parent, text=text, image=image, command=command, compound=compound,
            bd=0, relief="flat", highlightthickness=0, cursor="hand2",
            bg=c[bg_role], fg=c[tone],
            activebackground=c["btn_hover"], activeforeground=c["text"],
            disabledforeground=c["btn_disabled_fg"],
            font=font or self.f(), padx=padx, pady=pady,
        )
        if image is not None:
            button.image = image
        return button

    def _build_layout(self) -> None:
        c = self.colors
        parent = self.container

        self._build_topbar(parent)
        tk.Frame(parent, bg=c["border"], height=1).pack(fill="x")

        self.status_bar = tk.Frame(parent, bg=c["statusbar"], height=30)
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)
        tk.Label(self.status_bar, textvariable=self.status_var, bg=c["statusbar"],
                 fg=c["muted"], font=self.f(9), anchor="w").pack(side="left", padx=16)

        body = tk.Frame(parent, bg=c["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=12)

        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True)
        self._build_plans_tab(self.nb)
        self._build_stats_tab(self.nb)

    def _build_topbar(self, parent: tk.Frame) -> None:
        c = self.colors
        bar = tk.Frame(parent, bg=c["topbar"], height=58)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        gear = self._icon("gear_dark" if self.is_dark() else "gear_light")
        self.settings_btn = self._flat_button(
            bar, text="  设置", image=gear, command=self.open_settings,
        )
        self.settings_btn.pack(side="left", padx=(12, 0), pady=11)

        logo = self._icon("logo")
        if logo is not None:
            tk.Label(bar, image=logo, bg=c["topbar"]).pack(side="left", padx=(18, 9))
        tk.Label(bar, text=APP_NAME, bg=c["topbar"], fg=c["text"],
                 font=self.f(13, bold=True)).pack(side="left")
        tk.Label(bar, text=APP_SUBTITLE, bg=c["topbar"], fg=c["muted"],
                 font=self.f(9)).pack(side="left", padx=(8, 0))

        toggle_icon = self._icon("sun_dark" if self.is_dark() else "moon_light")
        self.theme_btn = self._flat_button(
            bar, text="  切换主题" if toggle_icon is None else "",
            image=toggle_icon, command=self.toggle_theme, padx=10,
        )
        self.theme_btn.pack(side="right", padx=12, pady=11)

    # ==================================================================
    # 计划管理页
    # ==================================================================
    def _build_plans_tab(self, nb: ttk.Notebook) -> None:
        c = self.colors
        tab = tk.Frame(nb, bg=c["bg"])
        nb.add(tab, text="  计划管理  ")

        self._build_toolbar(tab)

        paned = ttk.PanedWindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True, pady=(10, 0))

        left = self.card(paned)
        left_inner = tk.Frame(left, bg=c["panel"])
        left_inner.pack(fill="both", expand=True, padx=14, pady=14)

        right = self.card(paned)
        right_inner = tk.Frame(right, bg=c["panel"])
        right_inner.pack(fill="both", expand=True, padx=14, pady=14)

        paned.add(left, weight=5)
        paned.add(right, weight=5)

        self._build_plan_list(left_inner)
        self._build_detail(right_inner)

    def _build_toolbar(self, parent: tk.Frame) -> None:
        c = self.colors
        bar = self.card(parent)
        bar.pack(fill="x")
        inner = tk.Frame(bar, bg=c["panel"])
        inner.pack(fill="x", padx=14, pady=12)

        actions = tk.Frame(inner, bg=c["panel"])
        actions.pack(fill="x")

        ttk.Button(actions, text="+ 新建计划", style="Accent.TButton",
                   command=self.new_plan).pack(side="left")
        ttk.Button(actions, text="删除", command=self.delete_plan).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="标记完成", command=self.mark_done).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="导出 JSON", command=self.export_data).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="最小化到托盘", style="Ghost.TButton",
                   command=self.hide_to_tray).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="刷新", style="Ghost.TButton",
                   command=self.refresh_all).pack(side="right")

        filters = tk.Frame(inner, bg=c["panel"])
        filters.pack(fill="x", pady=(12, 0))

        self.label(filters, "搜索", tone="muted", size=self.font_size - 1).pack(
            side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        search = ttk.Entry(filters, textvariable=self.search_var, width=24)
        search.pack(side="left")

        self.label(filters, "状态", tone="muted", size=self.font_size - 1).pack(
            side="left", padx=(20, 6))
        self.filter_status = tk.StringVar(value="全部")
        ttk.Combobox(filters, textvariable=self.filter_status, values=FILTER_STATUS,
                     width=9, state="readonly").pack(side="left")

        self.label(filters, "分类", tone="muted", size=self.font_size - 1).pack(
            side="left", padx=(20, 6))
        self.filter_category = tk.StringVar(value="全部")
        self.category_box = ttk.Combobox(filters, textvariable=self.filter_category,
                                         values=["全部"], width=10, state="readonly")
        self.category_box.pack(side="left")

        self.label(filters, "排序", tone="muted", size=self.font_size - 1).pack(
            side="left", padx=(20, 6))
        self.sort_var = tk.StringVar(value=str(self.settings.get("default_order")))
        ttk.Combobox(filters, textvariable=self.sort_var, values=db.ORDER_OPTIONS,
                     width=8, state="readonly").pack(side="left")

        self.filter_status.trace_add("write", lambda *_: self.refresh_plans())
        self.filter_category.trace_add("write", lambda *_: self.refresh_plans())
        self.sort_var.trace_add("write", lambda *_: self.refresh_plans())
        search.bind("<KeyRelease>", lambda _e: self.refresh_plans())

    def _build_plan_list(self, parent: tk.Frame) -> None:
        c = self.colors
        head = tk.Frame(parent, bg=c["panel"])
        head.pack(fill="x", pady=(0, 10))
        self.label(head, "计划列表", size=self.font_size + 1, bold=True).pack(side="left")
        self.list_count = tk.StringVar(value="共 0 条")
        self.label(head, textvariable=self.list_count, tone="muted",
                   size=self.font_size - 1).pack(side="right")

        wrap = tk.Frame(parent, bg=c["panel"])
        wrap.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(wrap, columns=[col[0] for col in PLAN_COLUMNS],
                                 show="headings", selectmode="browse")
        for key, title, width, anchor in PLAN_COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "title"))
        self.tree.tag_configure("odd", background=c["panel"])
        self.tree.tag_configure("even", background=c["stripe"])
        self.tree.tag_configure("overdue", foreground=c["danger"])
        self.tree.tag_configure("today", foreground=c["warn"])
        self.tree.tag_configure("done", foreground=c["done_fg"])

        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_plan)

    def _build_detail(self, parent: tk.Frame) -> None:
        self.detail_nb = ttk.Notebook(parent, style="Detail.TNotebook")
        self.detail_nb.pack(fill="both", expand=True)

        self.tab_info = tk.Frame(self.detail_nb, bg=self.colors["panel"])
        self.tab_tasks = tk.Frame(self.detail_nb, bg=self.colors["panel"])
        self.tab_logs = tk.Frame(self.detail_nb, bg=self.colors["panel"])
        self.detail_nb.add(self.tab_info, text="计划详情")
        self.detail_nb.add(self.tab_tasks, text="子任务 (0)")
        self.detail_nb.add(self.tab_logs, text="进度记录 (0)")

        self._build_info_tab(self.tab_info)
        self._build_tasks_tab(self.tab_tasks)
        self._build_logs_tab(self.tab_logs)

    # ---------------------------------------------------------------- 详情
    def _build_info_tab(self, parent: tk.Frame) -> None:
        c = self.colors
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(4, weight=1)

        def field_label(text: str, row: int, col: int, anchor: str = "w") -> None:
            self.label(parent, text, tone="muted", size=self.font_size - 1).grid(
                row=row, column=col, sticky=anchor, padx=(0, 8), pady=7
            )

        def text_area(holder: tk.Frame, height: int) -> tk.Text:
            widget = tk.Text(
                holder, height=height, wrap="word", bd=0, relief="flat",
                highlightthickness=1, highlightbackground=c["entry_border"],
                highlightcolor=c["accent"], bg=c["entry_bg"], fg=c["text"],
                insertbackground=c["text"], selectbackground=c["accent"],
                selectforeground=c["accent_fg"], font=self.f(), padx=8, pady=6,
            )
            bar = ttk.Scrollbar(holder, orient="vertical", command=widget.yview)
            widget.configure(yscrollcommand=bar.set)
            widget.pack(side="left", fill="both", expand=True)
            bar.pack(side="right", fill="y")
            return widget

        self.var_title = tk.StringVar()
        self.var_category = tk.StringVar()
        self.var_priority = tk.StringVar(value="中")
        self.var_status = tk.StringVar(value="未开始")
        self.var_progress = tk.DoubleVar(value=0)

        field_label("计划标题", 0, 0)
        ttk.Entry(parent, textvariable=self.var_title).grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=7
        )

        field_label("分类", 1, 0)
        self.category_field = ttk.Combobox(parent, textvariable=self.var_category,
                                           values=["默认"], width=14)
        self.category_field.grid(row=1, column=1, sticky="w", pady=7)
        field_label("优先级", 1, 2)
        ttk.Combobox(parent, textvariable=self.var_priority, values=db.PRIORITIES,
                     width=12, state="readonly").grid(row=1, column=3, sticky="w", pady=7)

        field_label("状态", 2, 0)
        ttk.Combobox(parent, textvariable=self.var_status, values=db.STATUSES,
                     width=14, state="readonly").grid(row=2, column=1, sticky="w", pady=7)
        field_label("开始日期", 2, 2)
        self.dp_start = CalendarDateEntry(parent, c)
        self.dp_start.grid(row=2, column=3, sticky="w", pady=7)

        field_label("截止日期", 3, 0)
        self.dp_due = CalendarDateEntry(parent, c)
        self.dp_due.grid(row=3, column=1, sticky="w", pady=7)

        field_label("完成进度", 3, 2)
        prog = tk.Frame(parent, bg=c["panel"])
        prog.grid(row=3, column=3, sticky="ew", pady=7)
        prog.columnconfigure(0, weight=1)
        ttk.Scale(prog, from_=0, to=100, orient="horizontal",
                  variable=self.var_progress,
                  command=self._on_progress).grid(row=0, column=0, sticky="ew")
        self.progress_label = self.label(prog, "0%", size=self.font_size - 1, width=5)
        self.progress_label.grid(row=0, column=1, padx=(8, 0))

        field_label("计划说明", 4, 0, "nw")
        text_wrap = tk.Frame(parent, bg=c["panel"])
        text_wrap.grid(row=4, column=1, columnspan=3, sticky="nsew", pady=7)
        self.txt_desc = text_area(text_wrap, 6)

        self.meta_var = tk.StringVar()
        self.label(parent, textvariable=self.meta_var, tone="muted",
                   size=self.font_size - 1).grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(12, 0)
        )

        actions = tk.Frame(parent, bg=c["panel"])
        actions.grid(row=6, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Button(actions, text="保存修改", style="Accent.TButton",
                   command=self.save_plan).pack(side="left")
        ttk.Button(actions, text="放弃修改", command=self.reload_plan).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="标记为已完成", command=self.mark_done).pack(
            side="left", padx=(8, 0)
        )

    def _on_progress(self, _value: str = "") -> None:
        self.progress_label.configure(text=f"{int(round(self.var_progress.get()))}%")

    # ---------------------------------------------------------------- 子任务
    def _build_tasks_tab(self, parent: tk.Frame) -> None:
        c = self.colors
        row = tk.Frame(parent, bg=c["panel"])
        row.pack(fill="x")
        self.new_task_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.new_task_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self.add_task())
        ttk.Button(row, text="添加子任务", style="Accent.TButton",
                   command=self.add_task).pack(side="left", padx=(8, 0))

        self.label(parent, "双击子任务可切换完成状态；勾选后会按完成比例自动更新总进度。",
                   tone="muted", size=self.font_size - 1).pack(anchor="w", pady=(12, 8))

        wrap = tk.Frame(parent, bg=c["panel"])
        wrap.pack(fill="both", expand=True)
        self.tasks_tree = ttk.Treeview(wrap, columns=("done", "title"),
                                       show="headings", selectmode="browse")
        self.tasks_tree.heading("done", text="完成")
        self.tasks_tree.column("done", width=60, anchor="center", stretch=False)
        self.tasks_tree.heading("title", text="子任务")
        self.tasks_tree.column("title", width=380, anchor="w")
        self.tasks_tree.tag_configure("odd", background=c["panel"])
        self.tasks_tree.tag_configure("even", background=c["stripe"])
        self.tasks_tree.tag_configure("task_done", foreground=c["done_fg"])
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tasks_tree.yview)
        self.tasks_tree.configure(yscrollcommand=scroll.set)
        self.tasks_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tasks_tree.bind("<Double-1>", lambda _e: self.toggle_task())
        self.tasks_tree.bind("<space>", lambda _e: self.toggle_task())

        btns = tk.Frame(parent, bg=c["panel"])
        btns.pack(fill="x", pady=(12, 0))
        ttk.Button(btns, text="切换完成", command=self.toggle_task).pack(side="left")
        ttk.Button(btns, text="删除选中", command=self.delete_task).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="清除已完成", command=self.clear_done_tasks).pack(
            side="left", padx=(8, 0)
        )

    # ---------------------------------------------------------------- 记录
    def _build_logs_tab(self, parent: tk.Frame) -> None:
        c = self.colors
        self.label(parent, "记录一次进展 / 想法 / 复盘（自动记录时间）",
                   tone="muted", size=self.font_size - 1).pack(anchor="w", pady=(0, 8))

        self.log_text = tk.Text(
            parent, height=5, wrap="word", bd=0, relief="flat",
            highlightthickness=1, highlightbackground=c["entry_border"],
            highlightcolor=c["accent"], bg=c["entry_bg"], fg=c["text"],
            insertbackground=c["text"], selectbackground=c["accent"],
            selectforeground=c["accent_fg"], font=self.f(), padx=8, pady=6,
        )
        self.log_text.pack(fill="x")

        btns = tk.Frame(parent, bg=c["panel"])
        btns.pack(fill="x", pady=(10, 12))
        ttk.Button(btns, text="添加记录", style="Accent.TButton",
                   command=self.add_log).pack(side="left")
        ttk.Button(btns, text="删除选中", command=self.delete_log).pack(
            side="left", padx=(8, 0)
        )

        wrap = tk.Frame(parent, bg=c["panel"])
        wrap.pack(fill="both", expand=True)
        self.logs_tree = ttk.Treeview(wrap, columns=("time", "content"),
                                      show="headings", selectmode="browse")
        self.logs_tree.heading("time", text="时间")
        self.logs_tree.column("time", width=150, anchor="center", stretch=False)
        self.logs_tree.heading("content", text="记录内容")
        self.logs_tree.column("content", width=380, anchor="w")
        self.logs_tree.tag_configure("odd", background=c["panel"])
        self.logs_tree.tag_configure("even", background=c["stripe"])
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.logs_tree.yview)
        self.logs_tree.configure(yscrollcommand=scroll.set)
        self.logs_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ==================================================================
    # 统计页
    # ==================================================================
    def _build_stats_tab(self, nb: ttk.Notebook) -> None:
        c = self.colors
        tab = tk.Frame(nb, bg=c["bg"])
        nb.add(tab, text="  数据统计  ")
        self.stats_tab = tab

        cards = tk.Frame(tab, bg=c["bg"])
        cards.pack(fill="x")
        self.card_vars: dict[str, tk.StringVar] = {}
        specs = (
            ("total", "计划总数", c["accent"]),
            ("doing", "进行中", c["warn"]),
            ("done", "已完成", c["ok"]),
            ("overdue", "已逾期", c["danger"]),
        )
        for index, (key, title, color) in enumerate(specs):
            card = self.card(cards)
            card.pack(side="left", fill="both", expand=True,
                      padx=(0 if index == 0 else 12, 0))
            tk.Frame(card, bg=color, width=5).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=c["panel"])
            inner.pack(side="left", fill="both", expand=True, padx=18, pady=14)
            var = tk.StringVar(value="0")
            tk.Label(inner, textvariable=var, bg=c["panel"], fg=color,
                     font=self.f(self.font_size + 16, bold=True)).pack(anchor="w")
            tk.Label(inner, text=title, bg=c["panel"], fg=c["muted"],
                     font=self.f(self.font_size - 1)).pack(anchor="w", pady=(2, 0))
            self.card_vars[key] = var

        rate_card = self.card(tab)
        rate_card.pack(fill="x", pady=(14, 0))
        rate_row = tk.Frame(rate_card, bg=c["panel"])
        rate_row.pack(fill="x", padx=18, pady=16)
        self.label(rate_row, "总体完成率", bold=True).pack(side="left")
        self.rate_var = tk.DoubleVar(value=0)
        ttk.Progressbar(rate_row, variable=self.rate_var, maximum=100).pack(
            side="left", fill="x", expand=True, padx=14
        )
        self.rate_label = self.label(rate_row, "0%", bold=True)
        self.rate_label.pack(side="left")
        self.avg_label = self.label(rate_row, "", tone="muted", size=self.font_size - 1)
        self.avg_label.pack(side="right", padx=(14, 0))

        bottom = tk.Frame(tab, bg=c["bg"])
        bottom.pack(fill="both", expand=True, pady=(14, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        left = self.card(bottom)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        left_inner = tk.Frame(left, bg=c["panel"])
        left_inner.pack(fill="both", expand=True, padx=16, pady=14)
        self.label(left_inner, "分类统计", bold=True).pack(anchor="w", pady=(0, 10))
        self.category_tree = ttk.Treeview(
            left_inner, columns=("category", "n", "done", "avg"),
            show="headings", height=8,
        )
        for key, title, width in (
            ("category", "分类", 120), ("n", "计划数", 70),
            ("done", "已完成", 70), ("avg", "平均进度", 90),
        ):
            self.category_tree.heading(key, text=title)
            self.category_tree.column(key, width=width, anchor="center")
        self.category_tree.column("category", anchor="w")
        self.category_tree.tag_configure("odd", background=c["panel"])
        self.category_tree.tag_configure("even", background=c["stripe"])
        self.category_tree.pack(fill="both", expand=True)

        right = self.card(bottom)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        right_inner = tk.Frame(right, bg=c["panel"])
        right_inner.pack(fill="both", expand=True, padx=16, pady=14)
        self.label(right_inner, "最近记录", bold=True).pack(anchor="w", pady=(0, 10))
        self.recent_tree = ttk.Treeview(
            right_inner, columns=("time", "plan", "content"),
            show="headings", height=8,
        )
        for key, title, width in (
            ("time", "时间", 140), ("plan", "计划", 120), ("content", "内容", 220),
        ):
            self.recent_tree.heading(key, text=title)
            self.recent_tree.column(key, width=width, anchor="w")
        self.recent_tree.tag_configure("odd", background=c["panel"])
        self.recent_tree.tag_configure("even", background=c["stripe"])
        self.recent_tree.pack(fill="both", expand=True)

    # ==================================================================
    # 数据刷新
    # ==================================================================
    def refresh_all(self) -> None:
        self.refresh_categories()
        self.refresh_plans()
        self.refresh_stats()

    def refresh_categories(self) -> None:
        categories = self.db.list_categories()
        values = ["全部"] + categories
        self.category_box.configure(values=values)
        self.category_field.configure(values=categories or ["默认"])
        if self.filter_category.get() not in values:
            self.filter_category.set("全部")

    def _tags_for(self, row, index: int) -> list[str]:
        tags = ["even" if index % 2 else "odd"]
        if row["status"] == "已完成":
            tags.append("done")
        elif self.settings.get("highlight_due"):
            today = date.today().isoformat()
            due = row["due_date"]
            if due and due < today:
                tags.append("overdue")
            elif due == today:
                tags.append("today")
        return tags

    def refresh_plans(self) -> None:
        keep = self.current_plan_id
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        rows = self.db.list_plans(
            search=self.search_var.get().strip(),
            status=self.filter_status.get(),
            category=self.filter_category.get(),
            order=self.sort_var.get(),
        )
        for index, row in enumerate(rows):
            self.tree.insert(
                "", "end", iid=str(row["id"]),
                values=(row["title"], row["category"], row["priority"],
                        row["status"], row["due_date"] or "—",
                        f'{row["progress"]}%'),
                tags=self._tags_for(row, index),
            )
        self.list_count.set(f"共 {len(rows)} 条")

        if keep is not None and self.tree.exists(str(keep)):
            self.tree.selection_set(str(keep))
        elif rows:
            self.tree.selection_set(str(rows[0]["id"]))
        else:
            self.clear_detail()

    def _update_row(self, plan_id: int) -> None:
        iid = str(plan_id)
        if not self.tree.exists(iid):
            return
        plan = self.db.get_plan(plan_id)
        if plan is None:
            return
        children = self.tree.get_children()
        index = children.index(iid) if iid in children else 0
        self.tree.item(
            iid,
            values=(plan["title"], plan["category"], plan["priority"],
                    plan["status"], plan["due_date"] or "—",
                    f'{plan["progress"]}%'),
            tags=self._tags_for(plan, index),
        )

    def refresh_stats(self) -> None:
        data = self.db.stats()
        for key in ("total", "doing", "done", "overdue"):
            self.card_vars[key].set(str(data[key]))
        self.rate_var.set(data["rate"])
        self.rate_label.configure(text=f'{data["rate"]:.0f}%')
        self.avg_label.configure(text=f'平均进度 {data["avg_progress"]:.0f}%')

        for iid in self.category_tree.get_children():
            self.category_tree.delete(iid)
        for index, row in enumerate(self.db.category_stats()):
            self.category_tree.insert(
                "", "end",
                values=(row["category"], row["n"], row["done"] or 0,
                        f'{row["avg_progress"] or 0:.0f}%'),
                tags=("even" if index % 2 else "odd",),
            )

        for iid in self.recent_tree.get_children():
            self.recent_tree.delete(iid)
        for index, row in enumerate(self.db.recent_logs(30)):
            text = row["content"].replace("\n", " ")
            if len(text) > 40:
                text = text[:40] + "…"
            self.recent_tree.insert(
                "", "end",
                values=(row["created_at"], row["plan_title"] or "—", text),
                tags=("even" if index % 2 else "odd",),
            )

    # ==================================================================
    # 计划操作
    # ==================================================================
    def on_select_plan(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.current_plan_id = int(selection[0])
        self.load_plan(self.current_plan_id)

    def load_plan(self, plan_id: int) -> None:
        plan = self.db.get_plan(plan_id)
        if plan is None:
            return
        self.var_title.set(plan["title"])
        self.var_category.set(plan["category"])
        self.var_priority.set(plan["priority"])
        self.var_status.set(plan["status"])
        self.var_progress.set(plan["progress"])
        self._on_progress()
        self.dp_start.set(plan["start_date"])
        self.dp_due.set(plan["due_date"])
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("1.0", plan["description"] or "")
        self.meta_var.set(
            f'创建于 {plan["created_at"]}    更新于 {plan["updated_at"]}'
        )
        self.refresh_tasks()
        self.refresh_logs()

    def reload_plan(self) -> None:
        if self.current_plan_id is not None:
            self.load_plan(self.current_plan_id)
            self.set_status("已放弃未保存的修改")

    def clear_detail(self) -> None:
        self.current_plan_id = None
        self.var_title.set("")
        self.var_category.set("")
        self.var_priority.set("中")
        self.var_status.set("未开始")
        self.var_progress.set(0)
        self._on_progress()
        self.dp_start.set("")
        self.dp_due.set("")
        self.txt_desc.delete("1.0", "end")
        self.meta_var.set("尚未选择计划 —— 点击「+ 新建计划」开始")
        for iid in self.tasks_tree.get_children():
            self.tasks_tree.delete(iid)
        for iid in self.logs_tree.get_children():
            self.logs_tree.delete(iid)
        self.detail_nb.tab(self.tab_tasks, text="子任务 (0)")
        self.detail_nb.tab(self.tab_logs, text="进度记录 (0)")

    def new_plan(self) -> None:
        category = self.filter_category.get()
        if category == "全部":
            category = "默认"
        plan_id = self.db.add_plan(title="新计划", category=category)
        self.current_plan_id = plan_id
        self.refresh_categories()
        self.refresh_plans()
        self.tree.selection_set(str(plan_id))
        self.tree.see(str(plan_id))
        self.detail_nb.select(self.tab_info)
        self.set_status("已创建计划，填写详情后点击「保存修改」(Ctrl+S)")
        self.root.after(50, self._focus_title)

    def _focus_title(self) -> None:
        for child in self.tab_info.winfo_children():
            if isinstance(child, ttk.Entry):
                child.focus_set()
                child.selection_range(0, "end")
                return

    def save_plan(self) -> None:
        if self.current_plan_id is None:
            self.set_status("请先选择或新建一个计划")
            return
        title = self.var_title.get().strip() or "未命名计划"
        self.db.update_plan(
            self.current_plan_id,
            title=title,
            description=self.txt_desc.get("1.0", "end").strip(),
            category=self.var_category.get().strip() or "默认",
            priority=self.var_priority.get(),
            status=self.var_status.get(),
            start_date=self.dp_start.get() or None,
            due_date=self.dp_due.get() or None,
            progress=int(round(self.var_progress.get())),
        )
        self.refresh_categories()
        self._update_row(self.current_plan_id)
        self.refresh_stats()
        self.load_plan(self.current_plan_id)
        self.set_status(f'已保存「{title}」')

    def delete_plan(self) -> None:
        if self.current_plan_id is None:
            self.set_status("请先选择一个计划")
            return
        plan = self.db.get_plan(self.current_plan_id)
        if plan is None:
            return
        if self.settings.get("confirm_delete") and not messagebox.askyesno(
            "删除计划", f'确定删除「{plan["title"]}」及其子任务和记录吗？此操作不可撤销。'
        ):
            return
        plan_id = self.current_plan_id
        self.current_plan_id = None
        self.db.delete_plan(plan_id)
        self.refresh_categories()
        self.refresh_plans()
        self.refresh_stats()
        self.set_status("计划已删除")

    def mark_done(self) -> None:
        if self.current_plan_id is None:
            self.set_status("请先选择一个计划")
            return
        self.db.update_plan(self.current_plan_id, status="已完成", progress=100)
        self._update_row(self.current_plan_id)
        self.refresh_stats()
        self.load_plan(self.current_plan_id)
        self.set_status("已标记为完成")

    def export_data(self) -> None:
        default = f'blueprint_export_{datetime.now():%Y%m%d_%H%M}.json'
        try:
            os.makedirs(paths.EXPORT_DIR, exist_ok=True)
        except OSError:
            pass
        path = filedialog.asksaveasfilename(
            title="导出数据", defaultextension=".json",
            initialdir=paths.EXPORT_DIR, initialfile=default,
            filetypes=[("JSON 文件", "*.json")],
        )
        if not path:
            return
        count = self.db.export_json(path)
        self.set_status(f"已导出 {count} 条计划到 {path}")
        messagebox.showinfo("导出完成", f"已导出 {count} 条计划：\n{path}")

    # ==================================================================
    # 子任务操作
    # ==================================================================
    def refresh_tasks(self) -> None:
        for iid in self.tasks_tree.get_children():
            self.tasks_tree.delete(iid)
        if self.current_plan_id is None:
            return
        tasks = self.db.tasks_for(self.current_plan_id)
        for index, task in enumerate(tasks):
            tags = ["even" if index % 2 else "odd"]
            if task["done"]:
                tags.append("task_done")
            self.tasks_tree.insert(
                "", "end", iid=str(task["id"]),
                values=("✔" if task["done"] else "○", task["title"]),
                tags=tuple(tags),
            )
        self.detail_nb.tab(self.tab_tasks, text=f"子任务 ({len(tasks)})")

    def add_task(self) -> None:
        title = self.new_task_var.get().strip()
        if self.current_plan_id is None:
            self.set_status("请先选择一个计划")
            return
        if not title:
            return
        self.db.add_task(self.current_plan_id, title)
        self.new_task_var.set("")
        self._sync_task_progress()
        self.refresh_tasks()

    def _selected_task_id(self) -> int | None:
        selection = self.tasks_tree.selection()
        return int(selection[0]) if selection else None

    def toggle_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            return
        self.db.toggle_task(task_id)
        self._sync_task_progress()
        self.refresh_tasks()

    def delete_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            return
        self.db.delete_task(task_id)
        self._sync_task_progress()
        self.refresh_tasks()

    def clear_done_tasks(self) -> None:
        if self.current_plan_id is None:
            return
        self.db.clear_done_tasks(self.current_plan_id)
        self._sync_task_progress()
        self.refresh_tasks()

    def _sync_task_progress(self) -> None:
        """按子任务完成比例同步总进度。"""
        if self.current_plan_id is None:
            return
        if not self.settings.get("auto_sync_progress"):
            return
        percent = self.db.task_progress(self.current_plan_id)
        if percent is None:
            return
        self.db.update_plan(self.current_plan_id, progress=percent)
        self.var_progress.set(percent)
        self._on_progress()
        self._update_row(self.current_plan_id)
        self.refresh_stats()

    # ==================================================================
    # 记录操作
    # ==================================================================
    def refresh_logs(self) -> None:
        for iid in self.logs_tree.get_children():
            self.logs_tree.delete(iid)
        if self.current_plan_id is None:
            return
        logs = self.db.logs_for(self.current_plan_id)
        for index, log in enumerate(logs):
            text = log["content"].replace("\n", " ")
            if len(text) > 60:
                text = text[:60] + "…"
            self.logs_tree.insert(
                "", "end", iid=str(log["id"]),
                values=(log["created_at"], text),
                tags=("even" if index % 2 else "odd",),
            )
        self.detail_nb.tab(self.tab_logs, text=f"进度记录 ({len(logs)})")

    def add_log(self) -> None:
        if self.current_plan_id is None:
            self.set_status("请先选择一个计划")
            return
        content = self.log_text.get("1.0", "end").strip()
        if not content:
            return
        self.db.add_log(self.current_plan_id, content)
        self.log_text.delete("1.0", "end")
        self.refresh_logs()
        self.refresh_stats()
        self.set_status("记录已添加")

    def delete_log(self) -> None:
        selection = self.logs_tree.selection()
        if not selection:
            return
        self.db.delete_log(int(selection[0]))
        self.refresh_logs()
        self.refresh_stats()

    # ==================================================================
    # 设置
    # ==================================================================
    def open_settings(self) -> None:
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            self.dialog.focus_set()
            return
        self.dialog = SettingsDialog(self)

    # ==================================================================
    # 杂项
    # ==================================================================
    def set_status(self, message: str) -> None:
        self.status_var.set(message)


class SettingsDialog(tk.Toplevel):
    """设置窗口：主题模式 / 主题色 / 功能开关。"""

    _NON_PERSISTED = ("start_with_windows",)

    def __init__(self, app: PlanFlowApp) -> None:
        super().__init__(app.root)
        self.app = app
        self.snapshot = app.settings.snapshot()
        self._placed = False
        self._vars = {
            "confirm_delete": tk.BooleanVar(value=bool(app.settings.get("confirm_delete"))),
            "auto_sync_progress": tk.BooleanVar(
                value=bool(app.settings.get("auto_sync_progress"))),
            "highlight_due": tk.BooleanVar(value=bool(app.settings.get("highlight_due"))),
            "remember_geometry": tk.BooleanVar(
                value=bool(app.settings.get("remember_geometry"))),
            "default_order": tk.StringVar(value=str(app.settings.get("default_order"))),
            "font_size": tk.StringVar(value=str(app.settings.get("font_size"))),
            "minimize_to_tray": tk.BooleanVar(
                value=bool(app.settings.get("minimize_to_tray"))),
            "close_to_tray": tk.BooleanVar(value=bool(app.settings.get("close_to_tray"))),
            "hotkey_enabled": tk.BooleanVar(value=bool(app.settings.get("hotkey_enabled"))),
            "start_with_windows": tk.BooleanVar(value=startup.is_enabled()),
        }

        self.title("设置")
        self.transient(app.root)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.bind("<Escape>", lambda _e: self.on_cancel())

        self.rebuild()
        self.focus_set()

    # ---------------------------------------------------------------- 构建
    def rebuild(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        c = self.app.colors
        self.configure(bg=c["bg"])
        self._build()
        self._place()

    def _build(self) -> None:
        c = self.app.colors
        f = self.app.f

        header = tk.Frame(self, bg=c["topbar"])
        header.pack(fill="x")
        tk.Label(header, text="设置", bg=c["topbar"], fg=c["text"],
                 font=f(13, bold=True)).pack(side="left", padx=22, pady=14)
        tk.Label(header, text="外观与功能偏好", bg=c["topbar"], fg=c["muted"],
                 font=f(9)).pack(side="left", pady=16)
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")

        body = tk.Frame(self, bg=c["panel"])
        body.pack(fill="both", expand=True)

        # ----- 外观 -----
        appearance = self._section(body, "外观")
        self._mode_buttons = {}
        row = tk.Frame(appearance, bg=c["panel"])
        row.pack(fill="x", pady=(0, 12))
        tk.Label(row, text="主题模式", bg=c["panel"], fg=c["muted"],
                 font=f(10), width=10, anchor="w").pack(side="left")
        for value, title in THEME_LABELS:
            selected = self.app.settings.get("theme") == value
            button = tk.Button(
                row, text=title, bd=0, relief="flat", cursor="hand2",
                font=f(10), width=8, padx=8, pady=6,
                bg=c["accent"] if selected else c["btn_bg"],
                fg=c["accent_fg"] if selected else c["text"],
                activebackground=c["accent_hover"] if selected else c["btn_hover"],
                activeforeground=c["accent_fg"] if selected else c["text"],
                command=lambda v=value: self._pick_theme(v),
            )
            button.pack(side="left", padx=(0, 8))
            self._mode_buttons[value] = button

        accent_row = tk.Frame(appearance, bg=c["panel"])
        accent_row.pack(fill="x")
        tk.Label(accent_row, text="主题色", bg=c["panel"], fg=c["muted"],
                 font=f(10), width=10, anchor="w").pack(side="left")
        current = str(self.app.settings.get("accent")).lower()
        for name, value in ACCENTS:
            holder = tk.Frame(accent_row, bg=c["panel"])
            holder.pack(side="left", padx=(0, 8))
            canvas = tk.Canvas(holder, width=30, height=30, bg=c["panel"],
                               highlightthickness=0, bd=0, cursor="hand2")
            canvas.pack()
            selected = value.lower() == current
            outline = c["text"] if selected else c["panel"]
            canvas.create_oval(2, 2, 28, 28, fill=value, outline=outline, width=3)
            if selected:
                canvas.create_oval(11, 11, 19, 19, fill=c["accent_fg"], outline="")
            canvas.bind("<Button-1>", lambda _e, v=value: self._pick_accent(v))
            canvas.bind("<Enter>", lambda _e, cv=canvas, v=value: cv.itemconfigure(
                1, outline=self.app.colors["accent_hover"]))
            canvas.bind("<Leave>", lambda _e, cv=canvas, v=value, s=selected: cv.itemconfigure(
                1, outline=self.app.colors["text"] if s else self.app.colors["panel"]))

        # ----- 功能 -----
        options = self._section(body, "功能")
        for key, title in (
            ("confirm_delete", "删除计划前二次确认"),
            ("auto_sync_progress", "子任务完成时自动同步总进度"),
            ("highlight_due", "高亮显示逾期与今日到期的计划"),
            ("remember_geometry", "记住窗口大小与位置"),
        ):
            ttk.Checkbutton(options, text=title,
                            variable=self._vars[key]).pack(anchor="w")

        combo_row = tk.Frame(options, bg=c["panel"])
        combo_row.pack(fill="x", pady=(12, 0))
        tk.Label(combo_row, text="默认排序", bg=c["panel"], fg=c["muted"],
                 font=f(10), width=10, anchor="w").pack(side="left")
        ttk.Combobox(combo_row, textvariable=self._vars["default_order"],
                     values=db.ORDER_OPTIONS, width=12, state="readonly").pack(side="left")

        font_row = tk.Frame(options, bg=c["panel"])
        font_row.pack(fill="x", pady=(10, 0))
        tk.Label(font_row, text="界面字号", bg=c["panel"], fg=c["muted"],
                 font=f(10), width=10, anchor="w").pack(side="left")
        ttk.Combobox(font_row, textvariable=self._vars["font_size"],
                     values=[str(size) for size in FONT_SIZES],
                     width=12, state="readonly").pack(side="left")

        # ----- 托盘与启动 -----
        tray_box = self._section(body, "托盘与启动")
        for key, title in (
            ("minimize_to_tray", "最小化窗口时隐藏到系统托盘"),
            ("close_to_tray", "点击关闭按钮时隐藏到托盘（不退出）"),
            ("hotkey_enabled", f"启用全局热键 {tray_mod.HOTKEY_LABEL}"),
            ("start_with_windows", "开机时自动启动（最小化到托盘）"),
        ):
            ttk.Checkbutton(tray_box, text=title,
                            variable=self._vars[key]).pack(anchor="w")
        tk.Label(
            tray_box,
            text=f"热键在任意界面下生效：已收起到托盘时呼出；正在使用时收起。\n"
                 f"右键单击托盘图标可打开菜单并退出程序。\n"
                 f"数据目录：{paths.CONFIG_DIR}",
            bg=c["panel"], fg=c["muted"], font=f(9), justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # ----- 底部按钮 -----
        tk.Frame(self, bg=c["border"], height=1).pack(fill="x")
        footer = tk.Frame(self, bg=c["panel"])
        footer.pack(fill="x", padx=22, pady=16)
        ttk.Button(footer, text="恢复默认", style="Ghost.TButton",
                   command=self.on_reset).pack(side="left")
        ttk.Button(footer, text="打开配置文件夹", style="Ghost.TButton",
                   command=self._open_config_dir).pack(side="left", padx=(8, 0))
        ttk.Button(footer, text="保存", style="Accent.TButton",
                   command=self.on_save).pack(side="right")
        ttk.Button(footer, text="取消", command=self.on_cancel).pack(
            side="right", padx=(0, 8))

    def _open_config_dir(self) -> None:
        try:
            paths.open_config_dir()
        except OSError:
            self.app.set_status("无法打开配置文件夹")

    def _section(self, parent: tk.Frame, title: str) -> tk.Frame:
        c = self.app.colors
        wrap = tk.Frame(parent, bg=c["panel"])
        wrap.pack(fill="x", padx=22, pady=(16, 0))
        tk.Label(wrap, text=title, bg=c["panel"], fg=c["accent"],
                 font=self.app.f(10, bold=True)).pack(anchor="w")
        tk.Frame(wrap, bg=c["border"], height=1).pack(fill="x", pady=(6, 12))
        box = tk.Frame(wrap, bg=c["panel"])
        box.pack(fill="x")
        return box

    def _place(self) -> None:
        self.update_idletasks()
        if self._placed:
            return
        self._placed = True
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        root = self.app.root
        x = root.winfo_rootx() + max(0, (root.winfo_width() - width) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - height) // 3)
        self.geometry(f"+{x}+{y}")

    # ---------------------------------------------------------------- 交互
    def _pick_theme(self, mode: str) -> None:
        if self.app.settings.get("theme") == mode:
            return
        self.app.settings.set("theme", mode)
        self.app.settings.save()
        self.after(10, self.app.apply_settings)

    def _pick_accent(self, value: str) -> None:
        if str(self.app.settings.get("accent")).lower() == value.lower():
            return
        self.app.settings.set("accent", value)
        self.app.settings.save()
        self.after(10, self.app.apply_settings)

    def on_reset(self) -> None:
        self.snapshot = self.app.settings.snapshot()
        self.app.settings.reset()
        self.app.settings.save()
        for key, var in self._vars.items():
            if key in self._NON_PERSISTED:
                continue
            var.set(self.app.settings.get(key))
        self.after(10, self.app.apply_settings)

    def _apply_startup(self) -> None:
        want = bool(self._vars["start_with_windows"].get())
        if want == startup.is_enabled():
            return
        if startup.set_enabled(want):
            self.app.set_status("已开启开机自动启动" if want else "已关闭开机自动启动")
        else:
            self.app.set_status("开机启动设置失败，请检查注册表权限")

    def on_save(self) -> None:
        order_changed = (
            self._vars["default_order"].get() != self.app.settings.get("default_order")
        )
        values = {
            key: var.get()
            for key, var in self._vars.items()
            if key not in self._NON_PERSISTED
        }
        self.app.settings.update(values)
        self.app.settings.set("font_size", int(self._vars["font_size"].get()))
        self.app.settings.save()
        self._apply_startup()
        self.app.apply_settings()
        if order_changed:
            self.app.sort_var.set(self.app.settings.get("default_order"))
        self.app.set_status("设置已保存")
        self._close()

    def on_cancel(self) -> None:
        self.app.settings.data = dict(self.snapshot)
        self.app.apply_settings()
        self._close()

    def _close(self) -> None:
        self.app.dialog = None
        try:
            self.destroy()
        except tk.TclError:
            pass


def _wake_existing_instance(timeout: float = 15.0) -> bool:
    """请求已运行的实例把主窗口显示出来。

    已有实例刚启动时（开机自启、打包版解包期间）托盘窗口可能尚未建立，
    此时一次性唤醒会被丢弃，所以这里带重试。
    """
    deadline = time.monotonic() + timeout
    while True:
        if tray_mod.wake_existing_instance():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)


def main(start_hidden: bool = False) -> None:
    if not single_instance.acquire():
        if not start_hidden:
            _wake_existing_instance()
        return
    paths.ensure_config_dir()
    paths.migrate_legacy_data()
    winicon.set_app_user_model_id()
    root = tk.Tk()
    app = PlanFlowApp(root, start_hidden=start_hidden)
    app.status_var.set(
        f"就绪 · Ctrl+N 新建，Ctrl+S 保存，F5 刷新，Ctrl+, 设置，"
        f"{tray_mod.HOTKEY_LABEL} 呼出/收起"
    )
    try:
        root.mainloop()
    finally:
        single_instance.release()


if __name__ == "__main__":
    main()
