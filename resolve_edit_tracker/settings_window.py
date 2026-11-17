"""Settings window. Every change is applied and saved immediately, like the macOS app."""

from .i18n import tr
import os
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import fmt, winapi
from .ui_common import S, bring_to_front, set_window_icon, palette
from .themes import OPTIONS, normalize


class SettingsWindow:
    def __init__(self, root, app, on_play_sound, on_theme=None, on_language=None):
        self.root = root
        self.app = app
        self.on_play_sound = on_play_sound
        self.on_theme = on_theme
        self.on_language = on_language
        self.win = None

    def show(self):
        if self.win is not None:
            try:
                bring_to_front(self.win)
                return
            except tk.TclError:
                self.win = None
        app = self.app
        win = self.win = tk.Toplevel(self.root)
        win.title(tr("Stintory – Settings"))
        win.configure(bg=palette()["bg"])
        win.minsize(S(520), S(520))
        win.protocol("WM_DELETE_WINDOW", self._close)
        set_window_icon(win)

        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=palette()["bg"], highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        s = app.settings

        ttk.Label(inner,text=tr("Preferences"),font=(("Helvetica Neue" if __import__("sys").platform == "darwin" else "Segoe UI"),21,"bold")).pack(anchor="w",pady=(4,12))
        appearance = self._section(inner, tr("Appearance"))
        row = ttk.Frame(appearance)
        row.pack(fill="x")
        ttk.Label(row, text=tr("Color theme")).pack(side="left")
        self.theme_var = tk.StringVar(value=normalize(s.theme))
        self.theme_combo = ttk.Combobox(row, textvariable=self.theme_var, values=OPTIONS, state="readonly", width=16)
        self.theme_combo.pack(side="right")
        self.theme_combo.bind("<<ComboboxSelected>>", self._theme_changed)

        self._check(appearance, tr("Subtle interface animations"), "animations")

        # Language controls: UI language is persisted without interrupting an active session.
        from .i18n import LANGUAGES, code_for
        for attr, title in [('language',tr('Language')), ('invoiceLanguage',tr('Invoice language'))]:
            row = ttk.Frame(appearance); row.pack(fill='x',pady=4)
            ttk.Label(row,text=title).pack(side='left')
            var = tk.StringVar(value=LANGUAGES[getattr(s,attr)])
            cb = ttk.Combobox(row,textvariable=var,values=list(LANGUAGES.values()),state='readonly',width=24)
            cb.pack(side='right'); cb.bind('<<ComboboxSelected>>',lambda _,a=attr,v=var:self._language_changed(a,code_for(v.get())))

        # ---- Billing
        billing = self._section(inner, tr("Billing"))
        row = ttk.Frame(billing)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=tr("Default rate")).pack(side="left")
        ttk.Label(row, text=tr("per hour")).pack(side="right")
        self.rate_var = tk.StringVar(value=self._num(s.rate))
        ttk.Entry(row, textvariable=self.rate_var, width=9, justify="right").pack(side="right", padx=6)
        self.rate_var.trace_add("write", lambda *_: self._set_float("rate", self.rate_var))
        cur = ttk.Frame(billing); cur.pack(fill="x", pady=4)
        ttk.Label(cur, text=tr("Currency")).pack(side="left")
        self.cur_var = tk.StringVar()
        self.cur_combo = ttk.Combobox(cur, textvariable=self.cur_var, state="readonly", width=22)
        self.cur_combo.pack(side="right"); self.cur_combo.bind("<<ComboboxSelected>>", self._currency_changed)
        self.currency_hint = ttk.Label(billing, style="Small.TLabel", wraplength=S(420), justify="left", text=tr("Currency changes apply to new sessions. Set a new rate; no automatic conversion."))
        self.currency_hint.pack(fill="x", pady=(3,4))
        self._sync_currency()

        # ---- Per-project rates
        pr = self._section(inner, tr("Per-project rates"))
        self.pr_frame = ttk.Frame(pr)
        self.pr_frame.pack(fill="x")
        ttk.Label(pr, style="Small.TLabel", wraplength=S(420), justify="left",
                  text=tr("Leave blank to use the default rate. Changing a rate here does not alter time already recorded.")).pack(fill="x", pady=(4, 0))
        self._build_project_rates()

        # ---- Tracking
        tracking = self._section(inner, tr("Tracking"))
        self.front_var = self._check(tracking, tr("Only track while DaVinci Resolve is the active app"), "trackOnlyWhenFrontmost")
        ttk.Label(tracking, style="Small.TLabel", wraplength=S(420), justify="left",
                  text=tr("Switch to another app and the timer freezes; if you stay away for more than a minute the session is saved. "
                       "Playback inside Resolve still counts as working. Turn this off to track whenever a project is open.")).pack(fill="x", pady=(0, 6))
        row = ttk.Frame(tracking)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=tr("Idle stop")).pack(side="left")
        ttk.Label(row, text=tr("minutes")).pack(side="right")
        self.idle_var = tk.StringVar(value=str(s.idleMinutes))
        sp = ttk.Spinbox(row, from_=0, to=240, width=5, textvariable=self.idle_var, justify="right")
        sp.pack(side="right", padx=6)
        self.idle_var.trace_add("write", lambda *_: self._set_int("idleMinutes", self.idle_var, 0, 240))
        presets=ttk.Frame(tracking); presets.pack(fill='x',pady=(5,3))
        for text,value in [(tr('Off'),0),('2 min',2),('5 min',5),('10 min',10),('15 min',15)]:
            ttk.Button(presets,text=text,command=lambda v=value:self.idle_var.set(str(v))).pack(side='left',padx=(0,3))
        ttk.Label(tracking,style='Small.TLabel',wraplength=S(420),text=tr('Recommended: 5 minutes. Use 10–15 if you often review footage or think without touching the controls. Custom: 0–240 min.')).pack(fill='x',pady=(0,4))
        ttk.Label(tracking, style="Small.TLabel", wraplength=S(420), justify="left",
                  text=tr("Pause after this many minutes with no keyboard or mouse activity. Reviewing playback and Resolve's own "
                       "progress dialogs don't count as idle. 0 disables it.")).pack(fill="x", pady=(0, 6))
        self._check(tracking, tr("Keep tracking while Resolve is rendering"), "pauseDuringRenders")

        # ---- Notifications
        nt = self._section(inner, tr("Notifications"))
        self._check(nt, tr("Play a sound when tracking starts"), "playSoundOnStart")
        row = ttk.Frame(nt)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=tr("Sound")).pack(side="left")
        ttk.Button(row, text=tr("Preview"), command=lambda: self.on_play_sound(self.app.settings.soundName)).pack(side="right")
        sounds = winapi.list_sounds() or [s.soundName]
        if s.soundName not in sounds:
            sounds = [s.soundName] + sounds
        self.sound_var = tk.StringVar(value=s.soundName)
        cb = ttk.Combobox(row, textvariable=self.sound_var, values=sounds, state="readonly", width=28)
        cb.pack(side="right", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._set("soundName", self.sound_var.get()))
        self._check(nt, tr("Show a toast when resuming from idle"), "toastOnIdleResume")

        # ---- General
        gen = self._section(inner, tr("General"))
        ttk.Label(gen,style="Small.TLabel",wraplength=S(420),text=tr("Launch mode is selected by the installer. Linked mode exits with Resolve; resident mode waits for new projects.")).pack(fill="x",pady=(0,5))
        self._check(gen, tr("Show elapsed time in the tray tooltip"), "menuBarShowTime")
        row = ttk.Frame(gen)
        row.pack(fill="x", pady=(6, 2))
        ttk.Label(row, text=tr("History")).pack(side="left")
        ttk.Button(row, text=tr("Clear all…"), command=self._clear).pack(side="right")
        ttk.Button(row, text=tr("Import CSV…"), command=self._import).pack(side="right", padx=6)
        self.import_msg = ttk.Label(gen, style="Small.TLabel")
        self.import_msg.pack(fill="x")
        row = ttk.Frame(gen)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=tr("Data folder")).pack(side="left")
        ttk.Button(row, text=tr("Open data folder"), command=lambda: winapi.open_path(self.app.store_directory)).pack(side="right")

        # ---- Advanced
        adv = self._section(inner, tr("Advanced"))
        ttk.Label(adv, style="Small.TLabel", wraplength=S(420), justify="left",
                  text=tr("Python used for the Resolve helper. Leave empty for the default interpreter. Takes effect after restart.")).pack(fill="x")
        row = ttk.Frame(adv)
        row.pack(fill="x", pady=4)
        self.py_var = tk.StringVar(value=s.pythonPath)
        ttk.Entry(row, textvariable=self.py_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=tr("Browse…"), command=self._browse_python).pack(side="left", padx=(6, 0))
        self.py_var.trace_add("write", lambda *_: self._set("pythonPath", self.py_var.get().strip()))

        win.update_idletasks()
        win.geometry("%dx%d" % (S(500), min(S(700), win.winfo_screenheight() - S(120))))
        bring_to_front(win)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _num(v):
        return str(int(v)) if v == int(v) else str(v)

    def _section(self, parent, title):
        lf = ttk.LabelFrame(parent, text=title, padding=10)
        lf.pack(fill="x", pady=(0, 10), padx=(0, 6))
        return lf

    def _check(self, parent, text, key, after=None):
        var = tk.BooleanVar(value=getattr(self.app.settings, key))

        def changed():
            self._set(key, var.get())
            if after:
                after(var)
        ttk.Checkbutton(parent, text=text, variable=var, command=changed).pack(anchor="w", pady=2)
        return var

    def _sync_login(self, var):
        eff = self.app.settings.launchAtLogin
        if eff != var.get():
            var.set(eff)
            messagebox.showwarning("Launch at login", "Windows refused to change the startup entry.", parent=self.win)

    def _sync_currency(self):
        from .currencies import CURRENCIES, canonical, default_currency, currency_label
        s=self.app.settings
        auto=tr("Automatic")+" — "+currency_label(default_currency(s.language))
        current=canonical(s.currency)
        self.cur_combo['values']=[auto]+[currency_label(c) for c in sorted(set(CURRENCIES)|{current})]
        self.cur_var.set(auto if s.currencyMode=='auto' else currency_label(current))
        self.rate_var.set(self._num(s.rate))

    def _currency_changed(self,event=None):
        from .currencies import currency_from_label
        value=currency_from_label(self.cur_var.get())
        auto=self.cur_combo.current()==0
        self.app.update_settings(currencyMode='auto' if auto else 'manual', currency=value if not auto else self.app.settings.currency)
        self._sync_currency(); self._build_project_rates()

    def _language_changed(self,attr,code):
        changed = getattr(self.app.settings, attr) != code
        self._set(attr,code)
        if attr=='language' and changed:
            from .i18n import set_language
            set_language(self.app.settings.language)
            if hasattr(self,'cur_combo'):
                self._sync_currency(); self._build_project_rates()
            if self.on_language: self.on_language()

    def _theme_changed(self, event=None):
        name = normalize(self.theme_var.get())
        self._set("theme", name)
        if self.on_theme: self.on_theme(name)

    def _set(self, key, value):
        if getattr(self.app.settings, key) != value:
            self.app.update_settings(**{key: value})

    def _set_float(self, key, var):
        try:
            value=float(var.get().replace(",", "."))
            if math.isfinite(value) and value>=0: self._set(key,value)
        except ValueError:
            pass

    def _set_int(self, key, var, lo, hi):
        try:
            self._set(key, max(lo, min(hi, int(var.get()))))
        except ValueError:
            pass

    def _build_project_rates(self):
        for w in self.pr_frame.winfo_children():
            w.destroy()
        names = self.app.project_names
        if not names:
            ttk.Label(self.pr_frame, style="Small.TLabel", wraplength=S(420), justify="left",
                      text=tr("Projects will appear here once you've tracked time on them. Each one bills at the default rate unless you set an override.")).pack(fill="x")
            return
        for name in names:
            row = ttk.Frame(self.pr_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=name if len(name) < 40 else name[:39] + "…").pack(side="left")
            ttk.Button(row, text="✕", width=3, command=lambda n=name: self._reset_rate(n)).pack(side="right")
            current = self.app.settings.projectRates.get(name)
            var = tk.StringVar(value=self._num(current) if current is not None else "")
            ttk.Entry(row, textvariable=var, width=9, justify="right").pack(side="right", padx=6)
            var.trace_add("write", lambda *_, n=name, v=var: self._set_project_rate(n, v.get()))

    def _set_project_rate(self, name, text):
        rates = dict(self.app.settings.projectRates)
        t = text.strip().replace(",", ".")
        if not t:
            rates.pop(name, None)
        else:
            try:
                rates[name] = float(t)
            except ValueError:
                return
        self.app.update_settings(projectRates=rates)

    def _reset_rate(self, name):
        rates = dict(self.app.settings.projectRates)
        rates.pop(name, None)
        self.app.update_settings(projectRates=rates)
        self._build_project_rates()

    def _import(self):
        path = filedialog.askopenfilename(parent=self.win, title="Import CSV",
                                          filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except OSError:
            self.import_msg.configure(text=tr("Couldn't read that file"))
            return
        n = self.app.import_sessions(text)
        self.import_msg.configure(text="Imported %d session%s" % (n, "" if n == 1 else "s") if n else tr("Nothing imported"))
        self._build_project_rates()

    def _clear(self):
        if messagebox.askyesno(tr("Delete all history"), tr("Delete every recorded session? This cannot be undone."),
                               icon="warning", default="no", parent=self.win):
            self.app.clear_history()
            self._build_project_rates()

    def _browse_python(self):
        path = filedialog.askopenfilename(parent=self.win, title=tr("Select Python interpreter"),
                                          filetypes=[("All files", "*")])
        if path:
            self.py_var.set(os.path.normpath(path))

    def _close(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None
