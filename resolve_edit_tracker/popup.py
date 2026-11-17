"""The tray popup (the Windows counterpart of the macOS menu-bar dropdown)."""
import time
import tkinter as tk

from . import fmt, winapi
from .models import MANUALLY_PAUSED, IDLE_PAUSED, NOT_IN_PROJECT, TRACKING, page_display
from .ui_common import S, font, palette


class Popup:
    WIDTH = 330

    def __init__(self, root, app, on_history, on_settings, on_quit):
        self.root = root
        self.app = app
        self.on_history = on_history
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.win = None
        self.shown_at = 0.0
        self.last_hidden = 0.0
        self._anchor = None
        self._job = None

    @property
    def visible(self):
        return self.win is not None

    def toggle(self, anchor=None):
        if self.visible:
            self.hide()
        elif time.time() - self.last_hidden < 0.35:
            return          # this very click already closed us by moving focus to the tray
        else:
            self.show(anchor)

    # ------------------------------------------------------------------ build

    def show(self, anchor=None):
        if self.win is not None:
            return
        self._anchor = anchor
        P = self.P = palette()
        win = self.win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=P["border"])
        winapi.hide_from_taskbar(win)

        body = tk.Frame(win, bg=P["bg"], padx=S(14), pady=S(12))
        body.pack(fill="both", expand=True, padx=1, pady=1)

        # header
        head = tk.Frame(body, bg=P["bg"])
        head.pack(fill="x")
        self.dot = tk.Canvas(head, width=S(22), height=S(22), bg=P["bg"], highlightthickness=0)
        self.dot.pack(side="left", padx=(0, S(10)))
        mid = tk.Frame(head, bg=P["bg"])
        mid.pack(side="left", fill="x", expand=True)
        self.lbl_project = tk.Label(mid, text="", bg=P["bg"], fg=P["fg"], font=font(10, "bold"), anchor="w")
        self.lbl_project.pack(fill="x")
        self.lbl_status = tk.Label(mid, text="", bg=P["bg"], fg=P["muted"], font=font(8), anchor="w")
        self.lbl_status.pack(fill="x")
        self.lbl_elapsed = tk.Label(head, text="0:00:00", bg=P["bg"], fg=P["muted"], font=("Consolas", 14, "bold"))
        self.lbl_elapsed.pack(side="right")

        # connection warning (only packed when needed)
        self.warn = tk.Label(body, text="", bg=P["warn_bg"], fg=P["warn_fg"], font=font(8), justify="left",
                             anchor="w", padx=S(8), pady=S(6), wraplength=S(self.WIDTH - 50))

        self._sep(body)
        totals = tk.Frame(body, bg=P["bg"])
        totals.pack(fill="x")
        self.vals = {}
        for key, label in (("today", "Today"), ("week", "This week"),
                           ("project", "Project total"), ("earn", "Earnings")):
            row = tk.Frame(totals, bg=P["bg"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=P["bg"], fg=P["muted"], font=font(9)).pack(side="left")
            v = tk.Label(row, text="", bg=P["bg"], fg=P["fg"], font=font(9, "bold"))
            v.pack(side="right")
            self.vals[key] = v

        self.totals_frame = totals
        self.break_frame = tk.Frame(body, bg=P["bg"])
        self.break_frame.pack(fill="x")
        self._sep(self.break_frame)
        self.break_title = tk.Label(self.break_frame, text="WHERE YOUR TIME GOES", bg=P["bg"], fg=P["muted"],
                                    font=font(7, "bold"), anchor="w")
        self.break_title.pack(fill="x")
        self.canvas_w = S(self.WIDTH - 30)
        self.row_h = S(20)
        self.break_canvas = tk.Canvas(self.break_frame, width=self.canvas_w, height=self.row_h, bg=P["bg"],
                                      highlightthickness=0)
        self.break_canvas.pack(fill="x")

        self._sep(body)
        self.note_var = tk.StringVar(value=self.app.note_draft)
        self.note_var.trace_add("write", lambda *_: setattr(self.app, "note_draft", self.note_var.get()))
        self.note_entry = tk.Entry(body, textvariable=self.note_var, bg=P["card"], fg=P["fg"],
                                   insertbackground=P["fg"], relief="flat", font=font(9),
                                   highlightthickness=1, highlightbackground=P["border"], highlightcolor=P["primary"])
        self.note_entry.pack(fill="x", ipady=S(4), pady=(0, S(8)))
        self.note_hint = tk.Label(body, text="Session note (saved when the timer stops)", bg=P["bg"], fg=P["muted"],
                                  font=font(7), anchor="w")
        self.note_hint.pack(fill="x", pady=(0, S(8)))

        self.btn_pause = self._button(body, "Pause", self._pause, primary=True)
        row = tk.Frame(body, bg=P["bg"])
        row.pack(fill="x", pady=S(4))
        b1 = self._button(row, "History", lambda: self._and_close(self.on_history), pack=False)
        b2 = self._button(row, "Settings", lambda: self._and_close(self.on_settings), pack=False)
        b1.pack(side="left", fill="x", expand=True, padx=(0, S(3)))
        b2.pack(side="left", fill="x", expand=True, padx=(S(3), 0))
        self._button(body, "Quit Stintory", lambda: self._and_close(self.on_quit), danger=True)

        win.bind("<Escape>", lambda e: self.hide())
        self.refresh()
        self._place()
        win.deiconify()
        win.lift()
        try:
            win.focus_force()
        except tk.TclError:
            pass
        self.shown_at = time.time()
        self._had_focus = False
        self._forced = False
        self._job = self.root.after(250, self._poll)

    def _sep(self, parent):
        f = tk.Frame(parent, bg=self.P["border"], height=1)
        f.pack(fill="x", pady=S(9))
        return f

    def _button(self, parent, text, cmd, primary=False, danger=False, pack=True):
        P = self.P
        if primary:
            bg, hov, fg = P["primary"], P["primary_hover"], P["primary_fg"]
        else:
            bg, hov, fg = P["btn"], P["btn_hover"], (P["danger"] if danger else P["fg"])
        b = tk.Label(parent, text=text, bg=bg, fg=fg, font=font(9, "bold" if primary else "normal"),
                     pady=S(6), cursor="hand2")
        b._bg, b._hov, b._enabled = bg, hov, True
        b.bind("<Enter>", lambda e: b._enabled and b.configure(bg=b._hov))
        b.bind("<Leave>", lambda e: b.configure(bg=b._bg))
        b.bind("<Button-1>", lambda e: cmd() if b._enabled else None)
        if pack:
            b.pack(fill="x", pady=S(3))
        return b

    # ------------------------------------------------------------------ actions

    def _pause(self):
        self.app.toggle_pause()
        self.refresh()

    def _and_close(self, fn):
        self.hide()
        self.root.after(30, fn)

    def hide(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
            self.last_hidden = time.time()

    # ------------------------------------------------------------------ positioning / focus

    def _place(self):
        win = self.win
        win.update_idletasks()
        w = S(self.WIDTH)
        h = win.winfo_reqheight()
        area = winapi.work_area() or (0, 0, win.winfo_screenwidth(), win.winfo_screenheight())
        pos = self._anchor or winapi.cursor_pos()
        if pos:
            x = pos[0] - w // 2
            y = pos[1] - h - S(12)
            if y < area[1]:
                y = pos[1] + S(20)
        else:
            x = area[2] - w - S(12)
            y = area[3] - h - S(12)
        x = max(area[0] + S(8), min(x, area[2] - w - S(8)))
        y = max(area[1] + S(8), min(y, area[3] - h - S(8)))
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def _poll(self):
        """Close when the user clicks elsewhere (our process loses the foreground)."""
        self._job = None
        if self.win is None:
            return
        age = time.time() - self.shown_at
        info = winapi.foreground_info()
        if info is not None:
            if info[0] == self.app.own_pid:
                self._had_focus = True
            elif self._had_focus and age > 0.3:
                self.hide()
                return
            elif not self._had_focus and not self._forced and age > 0.3:
                self._forced = True                  # Windows refused focus: lift the restriction once
                winapi.force_foreground(self.win)
            elif not self._had_focus and age > 12:
                self.hide()                          # never got focus; don't linger forever
                return
        self.refresh()
        self._job = self.root.after(250, self._poll)

    # ------------------------------------------------------------------ refresh

    def refresh(self):
        if self.win is None:
            return
        app, P = self.app, self.P
        tracking = app.state == TRACKING
        kind = app.icon_kind
        color = {"tracking": P["accent"], "paused": P["muted"], "warning": "#f5a623"}.get(kind, P["muted"])
        c = self.dot
        c.delete("all")
        r = S(9)
        cx = S(11)
        c.create_oval(cx - r, cx - r, cx + r, cx + r, fill=color, outline="")
        if kind == "tracking":
            c.create_oval(cx - r * .4, cx - r * .4, cx + r * .4, cx + r * .4, fill="#ffffff", outline="")
        elif kind == "paused":
            for dx in (-S(3), S(1)):
                c.create_rectangle(cx + dx - 1, cx - S(4), cx + dx + S(2), cx + S(4), fill="#ffffff", outline="")
        elif kind == "warning":
            c.create_text(cx, cx, text="!", fill="#3c2800", font=font(10, "bold"))

        self.lbl_project.configure(text=app.status.project or app.stats.project or "Stintory")
        self.lbl_status.configure(text=app.status_line)
        self.lbl_elapsed.configure(text=fmt.hms(app.elapsed) if tracking else "0:00:00",
                                   fg=P["fg"] if tracking else P["muted"])

        detail = app.connection.detail
        if detail:
            self.warn.configure(text="⚠  " + detail)
            if not self.warn.winfo_ismapped():
                self.warn.pack(fill="x", pady=(S(8), 0), after=self.lbl_status.master.master)
        elif self.warn.winfo_ismapped():
            self.warn.pack_forget()

        st = app.stats
        self.vals["today"].configure(text=fmt.hms(st.today_sec))
        self.vals["week"].configure(text=fmt.hms(st.week_sec))
        self.vals["project"].configure(text=fmt.hms(st.project_total_sec))
        self.vals["earn"].configure(text=" / ".join(fmt.money(v,k) for k,v in sorted(st.project_money.items())) or "—")

        self._draw_breakdown(st.breakdown[:6])

        self.note_entry.configure(state="normal" if app.state != NOT_IN_PROJECT else "disabled")
        if self.note_var.get() != app.note_draft:
            self.note_var.set(app.note_draft)

        label = {TRACKING: "Pause", IDLE_PAUSED: "Resume", MANUALLY_PAUSED: "Resume"}.get(app.state, "Not tracking")
        enabled = not (app.state == NOT_IN_PROJECT and not app.status.has_project)
        self.btn_pause.configure(text=label)
        self.btn_pause._enabled = enabled
        self.btn_pause.configure(bg=P["primary"] if enabled else P["btn"],
                                 fg=P["primary_fg"] if enabled else P["muted"])
        self.btn_pause._bg = P["primary"] if enabled else P["btn"]

        self.win.update_idletasks()
        need = self.win.winfo_reqheight()
        if abs(need - self.win.winfo_height()) > 2:
            self.win.geometry("%dx%d" % (S(self.WIDTH), need))

    def _draw_breakdown(self, items):
        P = self.P
        show = bool(items)
        if show and not self.break_frame.winfo_ismapped():
            self.break_frame.pack(fill="x", after=self.totals_frame)
        elif not show and self.break_frame.winfo_ismapped():
            self.break_frame.pack_forget()
        if not show:
            return
        c = self.break_canvas
        c.delete("all")
        c.configure(height=self.row_h * len(items) + S(4))
        mx = max(v for _, v in items) or 1
        label_w, time_w = S(66), S(62)
        bar_x0, bar_x1 = label_w, self.canvas_w - time_w
        for i, (page, sec) in enumerate(items):
            y = i * self.row_h + self.row_h // 2 + S(2)
            c.create_text(0, y, text=page_display(page), anchor="w", fill=P["fg"], font=font(8))
            c.create_rectangle(bar_x0, y - S(3), bar_x1, y + S(3), fill=P["track"], outline="")
            c.create_rectangle(bar_x0, y - S(3), bar_x0 + max(S(3), (bar_x1 - bar_x0) * sec / mx), y + S(3),
                               fill=P["green"], outline="")
            c.create_text(self.canvas_w, y, text=fmt.hms(sec), anchor="e", fill=P["muted"], font=("Consolas", 8))
