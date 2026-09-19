"""自定义 Tkinter 组件：日历日期选择框（跟随应用主题）。"""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

WEEKDAYS = ("一", "二", "三", "四", "五", "六", "日")


class CalendarPopup(tk.Toplevel):
    """弹出式月历，选中某天回调 on_pick(date)。"""

    def __init__(self, master, initial: date, on_pick, anchor, colors: dict) -> None:
        super().__init__(master)
        self.colors = colors
        self.on_pick = on_pick
        self.year = initial.year
        self.month = initial.month
        self.selected = initial
        self._ready = False

        self.overrideredirect(True)
        self.configure(bg=colors["border"])

        self._body = tk.Frame(self, bg=colors["panel"])
        self._body.pack(padx=1, pady=1)

        self._build_header()

        self._grid = tk.Frame(self._body, bg=colors["panel"])
        self._grid.pack(padx=8, pady=(0, 8))
        self._render()

        self._place_near(anchor)
        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<FocusOut>", self._on_focus_out)
        self.after(150, self._activate)

    # -- 生命周期 ------------------------------------------------------
    def _activate(self) -> None:
        self._ready = True
        try:
            self.focus_set()
        except tk.TclError:
            pass

    def _on_focus_out(self, _event=None) -> None:
        if not self._ready:
            return
        focused = self.focus_get()
        if focused is not None:
            try:
                if str(focused).startswith(str(self)):
                    return
            except tk.TclError:
                pass
        self.close()

    def close(self) -> None:
        try:
            self.destroy()
        except tk.TclError:
            pass

    # -- 布局 ----------------------------------------------------------
    def _build_header(self) -> None:
        c = self.colors
        head = tk.Frame(self._body, bg=c["panel"])
        head.pack(fill="x", padx=8, pady=(8, 4))
        for text, command, side in (("<", self._prev, "left"), (">", self._next, "right")):
            tk.Button(
                head, text=text, bd=0, relief="flat", cursor="hand2",
                bg=c["panel"], fg=c["text"],
                activebackground=c["accent_soft"], activeforeground=c["accent"],
                command=command,
            ).pack(side=side)
        self._title = tk.Label(
            head, bg=c["panel"], fg=c["text"], width=12, font=("", 10, "bold")
        )
        self._title.pack(side="left", expand=True)

    def _render(self) -> None:
        c = self.colors
        for child in self._grid.winfo_children():
            child.destroy()
        self._title.configure(text=f"{self.year}年{self.month}月")

        for col, name in enumerate(WEEKDAYS):
            tk.Label(
                self._grid, text=name, width=3, bg=c["panel"], fg=c["muted"]
            ).grid(row=0, column=col, pady=(0, 4))

        today = date.today()
        cal = calendar.Calendar(firstweekday=0)
        for r, week in enumerate(cal.monthdayscalendar(self.year, self.month), start=1):
            for cidx, day in enumerate(week):
                if day == 0:
                    tk.Label(self._grid, text="", width=3, bg=c["panel"]).grid(
                        row=r, column=cidx
                    )
                    continue
                current = date(self.year, self.month, day)
                btn = tk.Button(
                    self._grid, text=str(day), width=3, bd=0, relief="flat",
                    bg=c["panel"], fg=c["text"], cursor="hand2",
                    activebackground=c["accent_soft"], activeforeground=c["accent"],
                    command=lambda d=current: self._pick(d),
                )
                if current == self.selected:
                    btn.configure(bg=c["accent"], fg=c["accent_fg"],
                                  activebackground=c["accent_hover"],
                                  activeforeground=c["accent_fg"])
                elif current == today:
                    btn.configure(bg=c["accent_soft"], fg=c["accent"], font=("", 9, "bold"))
                btn.grid(row=r, column=cidx, padx=1, pady=1)

    def _place_near(self, anchor) -> None:
        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        self.geometry(f"+{x}+{y}")

    # -- 交互 ----------------------------------------------------------
    def _prev(self) -> None:
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self._render()

    def _next(self) -> None:
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self._render()

    def _pick(self, value: date) -> None:
        self.on_pick(value)
        self.close()


class CalendarDateEntry(ttk.Frame):
    """输入框 + 日历按钮，文本格式 YYYY-MM-DD。"""

    def __init__(self, master, colors: dict, width: int = 12, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.colors = colors
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left", fill="x", expand=True)
        self.btn = ttk.Button(self, text="日历", width=5, command=self.open_calendar)
        self.btn.pack(side="left", padx=(2, 0))
        self._popup: CalendarPopup | None = None

    def open_calendar(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.close()
            self._popup = None
            return
        initial = self.get_date() or date.today()
        self._popup = CalendarPopup(
            self.winfo_toplevel(), initial, self._on_pick, self.entry, self.colors
        )

    def _on_pick(self, value: date) -> None:
        self.var.set(value.isoformat())
        self._popup = None

    def get_date(self) -> date | None:
        text = self.var.get().strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def get(self) -> str:
        value = self.get_date()
        return value.isoformat() if value else ""

    def set(self, value: str | None) -> None:
        self.var.set(value or "")

    def set_state(self, state: str) -> None:
        self.entry.configure(state=state)
        self.btn.configure(state=state)
