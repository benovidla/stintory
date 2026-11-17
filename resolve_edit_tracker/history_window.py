"""History & Reports window: list, add / edit / delete sessions, export CSV and timesheet."""

from .i18n import tr
import os
import math
import copy
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, ttk

from . import fmt, winapi
from .models import PAGES, page_display
from .timesheet import ReportRange, build_html
from .ui_common import S, bring_to_front, set_window_icon, palette

DATE_FMT = "%Y-%m-%d"


class HistoryWindow:
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self.win = None
        self._seen_version = -1
        self._job = None

    def show(self):
        if self.win is not None:
            try:
                bring_to_front(self.win)
                return
            except tk.TclError:
                self.win = None
        win = self.win = tk.Toplevel(self.root)
        win.title(tr("Stintory – History"))
        win.configure(bg=palette()["bg"])
        ttk.Label(win,text=tr("Activity history"),font=(("Helvetica Neue" if __import__("sys").platform == "darwin" else "Segoe UI"),21,"bold"),padding=(16,12)).pack(anchor="w")
        win.minsize(S(640), S(380))
        win.geometry("%dx%d" % (S(780), S(480)))
        win.protocol("WM_DELETE_WINDOW", self._close)
        set_window_icon(win)

        cols = ("when", "project", "duration", "earnings", "note")
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        for key, title, width, anchor in (("when", tr("When"), 130, "w"), ("project", tr("Project"), 180, "w"),
                                          ("duration", tr("Duration"), 80, "e"), ("earnings", tr("Earnings"), 90, "e"),
                                          ("note", tr("Note"), 260, "w")):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=S(width), anchor=anchor, stretch=(key in ("project", "note")))
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit())
        self.tree.bind("<Return>", lambda e: self._edit())
        self.tree.bind("<Delete>", lambda e: self._delete())
        self.tree.bind("<Button-3>", self._context)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._sync_buttons())

        bar = ttk.Frame(win, padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text=tr("＋ Add entry"), command=self._add).pack(side="left")
        self.btn_edit = ttk.Button(bar, text=tr("Edit"), command=self._edit)
        self.btn_edit.pack(side="left", padx=6)
        self.btn_del = ttk.Button(bar, text=tr("Delete"), command=self._delete)
        self.btn_del.pack(side="left")
        ttk.Button(bar, text=tr("Invoice PDF"), command=lambda: self._invoice()).pack(side="right", padx=6)
        ttk.Button(bar, text=tr("Timesheet…"), command=self._timesheet).pack(side="right")
        ttk.Button(bar, text=tr("Data folder"), command=lambda: winapi.open_path(self.app.store_directory)).pack(side="right", padx=6)
        ttk.Button(bar, text="CSV", command=self._csv).pack(side="right", padx=6)
        self.count = ttk.Label(bar, style="Small.TLabel")
        self.count.pack(side="right", padx=10)

        self.menu = tk.Menu(win, tearoff=False)
        self.menu.add_command(label=tr("Edit…"), command=self._edit)
        self.menu.add_command(label=tr("Delete"), command=self._delete)

        self._seen_version = -1
        self.refresh()
        self._poll()
        bring_to_front(win)

    def _close(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.win is not None:
            self.win.destroy()
            self.win = None

    def _poll(self):
        self._job = None
        if self.win is None:
            return
        if self.app.store.version != self._seen_version:
            self.refresh()
        self._job = self.root.after(1000, self._poll)

    def refresh(self):
        if self.win is None:
            return
        keep = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        rows = sorted(self.app.sessions, key=lambda s: s.start, reverse=True)
        for s in rows:
            note = "manual entry" if (not s.note and s.manual) else s.note
            self.tree.insert("", "end", iid=s.id, values=(
                fmt.session_date(s.start), s.project, fmt.hms(s.duration_sec),
                fmt.money(s.earnings, s.currency), note))
        still = [i for i in keep if self.tree.exists(i)]
        if still:
            self.tree.selection_set(still)
        self.count.configure(text="%d session%s" % (len(rows), "" if len(rows) == 1 else "s"))
        self._seen_version = self.app.store.version
        self._sync_buttons()

    def _sync_buttons(self):
        n = len(self.tree.selection())
        self.btn_edit.state(["!disabled"] if n == 1 else ["disabled"])
        self.btn_del.state(["!disabled"] if n >= 1 else ["disabled"])

    def _context(self, event):
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if self.tree.selection():
            self.menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------ actions

    def _selected(self):
        ids = set(self.tree.selection())
        return [s for s in self.app.sessions if s.id in ids]

    def _add(self):
        SessionDialog(self.win, self.app, None, self._after_edit)

    def _edit(self):
        sel = self._selected()
        if len(sel) == 1:
            SessionDialog(self.win, self.app, sel[0], self._after_edit)

    def _after_edit(self):
        self.refresh()

    def _delete(self):
        sel = self._selected()
        if not sel:
            return
        if len(sel) > 1 and not messagebox.askyesno(
                tr("Delete sessions"), tr("Delete %d sessions?") % len(sel), parent=self.win, default="no"):
            return
        self.app.delete_sessions([s.id for s in sel])
        self.refresh()

    def _csv(self):
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".csv",
                                            initialfile="stintory-sessions.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            try:
                with open(path, "w", encoding="utf-8-sig", newline="") as f:     # BOM so Excel shows € correctly
                    f.write(self.app.export_csv())
            except OSError as e:
                messagebox.showerror(tr("Export failed"), str(e), parent=self.win)

    def _invoice(self):
        from .invoice import InvoiceWindow
        InvoiceWindow(self.win,self.app,None)

    def _timesheet(self):
        TimesheetDialog(self.win, self.app, self._export_timesheet)

    def _export_timesheet(self, rng):
        html = build_html(self.app.sessions, rng, self.app.settings.currency)
        name = (rng.project or "all-projects").replace(" ", "-")
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".html",
                                            initialfile="timesheet-%s.html" % name,
                                            filetypes=[("HTML", "*.html")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
                winapi.open_path(path)
            except OSError as e:
                messagebox.showerror(tr("Export failed"), str(e), parent=self.win)


class _Modal(tk.Toplevel):
    def __init__(self, parent, title, width):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        set_window_icon(self)
        self.body = ttk.Frame(self, padding=14)
        self.body.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)
        self._width = width

    def finish(self):
        self.update_idletasks()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        self.geometry("+%d+%d" % (px + 60, py + 60))
        self.deiconify()
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())


class SessionDialog(_Modal):
    def __init__(self, parent, app, session, on_done):
        super().__init__(parent, tr("Edit session") if session else tr("Add a session"), 400)
        self.app, self.session, self.on_done = app, session, on_done
        b = self.body
        names = app.project_names
        self.project = tk.StringVar(value=session.project if session else (names[0] if names else ""))
        start = session.start if session else datetime.now().timestamp()
        self.start = tk.StringVar(value=fmt.session_date(start))
        mins = round(session.duration_sec / 60) if session else 30
        self.minutes = tk.StringVar(value=str(mins))
        if session and session.page_seconds:
            top = max(session.page_seconds.items(), key=lambda kv: kv[1])[0]
        else:
            top = "edit"
        self.page = tk.StringVar(value=page_display(top))
        self.note = tk.StringVar(value=session.note if session else "")
        self._orig_minutes = str(mins)
        self._orig_page = self.page.get()

        ttk.Label(b, text=tr("Edit session") if session else tr("Add a session"), font=(("Helvetica Neue" if __import__("sys").platform == "darwin" else "Segoe UI"), 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        rows = [(tr("Project"), ttk.Combobox(b, textvariable=self.project, values=names, width=34)),
                (tr("Start (YYYY-MM-DD HH:MM)"), ttk.Entry(b, textvariable=self.start, width=36)),
                (tr("Duration (minutes)"), ttk.Spinbox(b, from_=0, to=1440, increment=5, textvariable=self.minutes, width=10)),
                (tr("Page"), ttk.Combobox(b, textvariable=self.page, values=[page_display(p) for p in PAGES],
                                      state="readonly", width=16)),
                (tr("Note"), ttk.Entry(b, textvariable=self.note, width=36))]
        for i, (label, widget) in enumerate(rows, start=1):
            ttk.Label(b, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            widget.grid(row=i, column=1, sticky="ew", pady=4)
        self.err = ttk.Label(b, foreground="#c93b3b")
        self.err.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(b)
        btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text=tr("Cancel"), command=self.destroy).pack(side="left", padx=6)
        ttk.Button(btns, text=tr("Save") if session else tr("Add"), command=self._save).pack(side="left")
        self.bind("<Return>", lambda e: self._save())
        self.finish()

    def _save(self):
        project = self.project.get().strip()
        if not project:
            self.err.configure(text=tr("Enter a project name"))
            return
        try:
            start = fmt.parse_session_date(self.start.get())
        except ValueError:
            self.err.configure(text=tr("Start must look like 2026-03-01 14:30"))
            return
        try:
            minutes = float(self.minutes.get().replace(",", "."))
            if not math.isfinite(minutes) or minutes < 0:
                raise ValueError
        except ValueError:
            self.err.configure(text=tr("Duration must be a number of minutes"))
            return
        page = next((p for p in PAGES if page_display(p) == self.page.get()), "edit")
        note = self.note.get().strip()
        if self.session is None:
            self.app.add_manual_session(project, start, minutes, note, page)
        else:
            s = copy.deepcopy(self.session)
            old_project = s.project
            untouched = (self.minutes.get().strip() == self._orig_minutes and self.page.get() == self._orig_page)
            s.project, s.start, s.note = project, start, note
            if not untouched:                    # only rewrite the time split when the user actually changed it
                s.duration_sec = minutes * 60
                s.page_seconds = {page: minutes * 60}
                s.timeline_seconds = {}          # a hand-edited session no longer claims timeline splits
            # Moving old work never silently changes its historical rate or currency.
            self.app.update_session(s)
        self.destroy()
        self.on_done()


class TimesheetDialog(_Modal):
    def __init__(self, parent, app, on_export):
        super().__init__(parent, tr("Export timesheet"), 420)
        self.on_export = on_export
        b = self.body
        names = [tr("All projects")] + app.project_names
        self.project = tk.StringVar(value=tr("All projects"))
        today = date.today()
        self.from_var = tk.StringVar(value=(today - timedelta(days=30)).strftime(DATE_FMT))
        self.to_var = tk.StringVar(value=today.strftime(DATE_FMT))
        ttk.Label(b, text=tr("Export timesheet"), font=(("Helvetica Neue" if __import__("sys").platform == "darwin" else "Segoe UI"), 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Label(b, text=tr("Project")).grid(row=1, column=0, sticky="w", pady=4, padx=(0, 10))
        ttk.Combobox(b, textvariable=self.project, values=names, state="readonly", width=32).grid(row=1, column=1, sticky="ew")
        ttk.Label(b, text=tr("From (YYYY-MM-DD)")).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(b, textvariable=self.from_var, width=14).grid(row=2, column=1, sticky="w")
        ttk.Label(b, text=tr("To (YYYY-MM-DD)")).grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(b, textvariable=self.to_var, width=14).grid(row=3, column=1, sticky="w")
        quick = ttk.Frame(b)
        quick.grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Button(quick, text=tr("Last 7 days"), command=self._last7).pack(side="left")
        ttk.Button(quick, text=tr("This month"), command=self._month).pack(side="left", padx=6)
        self.err = ttk.Label(b, foreground="#c93b3b")
        self.err.grid(row=5, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(b)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text=tr("Cancel"), command=self.destroy).pack(side="left", padx=6)
        ttk.Button(btns, text=tr("Export…"), command=self._go).pack(side="left")
        self.bind("<Return>", lambda e: self._go())
        self.finish()

    def _last7(self):
        t = date.today()
        self.from_var.set((t - timedelta(days=7)).strftime(DATE_FMT))
        self.to_var.set(t.strftime(DATE_FMT))

    def _month(self):
        t = date.today()
        self.from_var.set(t.replace(day=1).strftime(DATE_FMT))
        self.to_var.set(t.strftime(DATE_FMT))

    def _go(self):
        try:
            a = datetime.strptime(self.from_var.get().strip(), DATE_FMT).date()
            z = datetime.strptime(self.to_var.get().strip(), DATE_FMT).date()
        except ValueError:
            self.err.configure(text=tr("Dates must look like 2026-03-31"))
            return
        if z < a:
            a, z = z, a
        proj = None if self.project.get() == tr("All projects") else self.project.get()
        self.destroy()
        self.on_export(ReportRange(proj, a, z))
