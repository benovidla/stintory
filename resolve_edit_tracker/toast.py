"""A small borderless panel that slides down from the top of the screen, holds a few seconds,
then fades out. Click-through and non-activating so it never steals focus from Resolve."""
import tkinter as tk

from . import winapi
from .ui_common import S, font, palette

HOLD_MS = 3800
KEY = "#010203"        # colour key for the rounded corners


class Toast:
    def __init__(self, root):
        self.root = root
        self.win = None
        self._jobs = []

    def _cancel(self):
        for j in self._jobs:
            try:
                self.root.after_cancel(j)
            except Exception:
                pass
        self._jobs = []

    def show(self, title, subtitle, kind="record", play_sound=False, sound_name="", animate=True):
        self._cancel()
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
        P = palette()
        w, h = S(310), S(74)
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        win.configure(bg=KEY)
        c = tk.Canvas(win, width=w, height=h, bg=KEY, highlightthickness=0, bd=0)
        c.pack()
        self._round_rect(c, 1, 1, w - 1, h - 1, S(14), fill=P["card"], outline=P["border"])
        cx, cy, r = S(38), h // 2, S(14)
        color = P["accent"] if kind == "record" else P["primary"]
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
        if kind == "record":
            c.create_oval(cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42, fill="#ffffff", outline="")
        else:
            c.create_text(cx, cy, text="⇄", fill="#ffffff", font=font(11, "bold"))
        c.create_text(S(66), h // 2 - S(10), text=title, anchor="w", fill=P["fg"], font=font(11, "bold"))
        c.create_text(S(66), h // 2 + S(11), text=self._fit(subtitle, 30), anchor="w", fill=P["muted"], font=font(9))

        win.update_idletasks()
        area = winapi.work_area()
        sw = area[2] - area[0] if area else win.winfo_screenwidth()
        left = (area[0] if area else 0) + (sw - w) // 2
        top = (area[1] if area else 0) + S(22)
        win.geometry("%dx%d+%d+%d" % (w, h, left, top - S(18)))
        win.attributes("-alpha", 0.0)
        win.deiconify()
        win.update_idletasks()
        winapi.make_toast_window(win)
        self.win = win

        if play_sound and sound_name:
            winapi.play_sound(sound_name)

        if animate:
            self._animate_in(win, left, top, 0)
        else:
            win.attributes("-alpha",1.0); win.geometry("+%d+%d"%(left,top))
            self._jobs.append(self.root.after(HOLD_MS,win.destroy))

    @staticmethod
    def _fit(text, n):
        return text if len(text) <= n else text[: n - 1] + "…"

    @staticmethod
    def _round_rect(c, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return c.create_polygon(pts, smooth=True, **kw)

    def _animate_in(self, win, left, top, step, steps=10):
        if win is not self.win:
            return
        t = (step + 1) / steps
        ease = 1 - (1 - t) ** 3
        try:
            win.attributes("-alpha", min(1.0, ease))
            win.geometry("+%d+%d" % (left, int(top - S(18) * (1 - ease))))
        except tk.TclError:
            return
        if step + 1 < steps:
            self._jobs.append(self.root.after(18, self._animate_in, win, left, top, step + 1))
        else:
            self._jobs.append(self.root.after(HOLD_MS, self._animate_out, win, 0))

    def _animate_out(self, win, step, steps=14):
        if win is not self.win:
            return
        try:
            win.attributes("-alpha", max(0.0, 1.0 - (step + 1) / steps))
        except tk.TclError:
            return
        if step + 1 < steps:
            self._jobs.append(self.root.after(30, self._animate_out, win, step + 1))
        else:
            try:
                win.destroy()
            except tk.TclError:
                pass
            self.win = None
