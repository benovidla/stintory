"""Glue: tk root (UI thread), tray icon (pystray thread), Resolve monitor (worker thread)."""

from .i18n import tr
import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback

from . import winapi
from .history_window import HistoryWindow
from .monitor import ResolveMonitor
from .dashboard import Dashboard
from .settings_window import SettingsWindow
from .state import AppState
from .toast import Toast
from .ui_common import Scale, apply_ttk_theme, make_icon_image, set_window_icon
from .util import Log, signal_dir


def launch_command():
    return ""  # startup at Windows login is intentionally disabled


class TrackerApp:
    GONE_GRACE_SEC = 2          # --with-resolve: quit this long after Resolve closed
    NEVER_STARTED_SEC = 120      # --with-resolve: give up if Resolve never shows up

    def __init__(self, simulate=False, use_tray=True, with_resolve=False, background=False, offline=False, manual=False):
        winapi.set_app_identity()
        winapi.set_dpi_aware()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Stintory")
        Scale.init(self.root)
        apply_ttk_theme(self.root)
        set_window_icon(self.root)
        self.root.report_callback_exception = self._tk_error
        self.q = queue.Queue()
        self.icon = None
        self._last_kind = None
        self._last_title = None
        self._last_pause_label = None
        self.with_resolve = with_resolve
        self.background = background
        self.offline = offline
        self.manual = manual
        self._monitor_started = False
        self.simulate = simulate
        self.started_at = time.time()
        self.resolve_seen = False
        self.resolve_gone_since = None
        self._os_resolve_missing = False
        self._quitting = False
        self.open_flag = os.path.join(signal_dir(), "open.panel")

        self.toast = Toast(self.root)
        self.state = AppState(toast_fn=lambda **kw: self.toast.show(animate=self.state.settings.animations, **kw), launch_command=launch_command(), **({"autostart_get": lambda: False, "autostart_set": lambda enabled, command: False} if simulate else {}))
        if simulate:
            from .models import Session
            now = time.time()
            self.state.settings.trackOnlyWhenFrontmost = False
            self.state.settings.playSoundOnStart = False
            self.state.idle_fn = lambda: 0
            if not self.state.sessions:
                for project, timelines in [('Demo Project', {'Main Edit': 7320, 'Social Cutdowns': 2940, 'Teaser': 1380}), ('Studio Campaign', {'Hero Film': 14760, 'Vertical 01': 5220}), ('Wedding Film', {'Highlights': 9180, 'Ceremony': 4380})]:
                    total = sum(timelines.values())
                    self.state.store.append(Session(project, now-86400-total, now-86400, total, 35, '€', page_seconds={'edit':total*.57,'color':total*.25,'fairlight':total*.12,'deliver':total*.06},timeline_seconds=timelines))
                self.state._rebuild_stats(force=True)
        from .i18n import set_language
        set_language(self.state.settings.language)
        self.popup = Dashboard(self.root, self.state, self.open_history, self.open_settings, self.quit, hide_request=self.hide_window)
        self.settings_win = SettingsWindow(self.root, self.state, winapi.play_sound, self.popup.apply_theme, self._schedule_language_refresh)
        self._language_job = None
        self.history_win = HistoryWindow(self.root, self.state)

        if sys.platform == "darwin":
            self.root.createcommand("::tk::mac::ReopenApplication", lambda: self.popup.show())
            self.root.createcommand("::tk::mac::Quit", self.quit)
        self.monitor = ResolveMonitor(
            lambda status, conn: self.q.put(lambda: self._receive_status(status, conn)),
            python_path=self.state.settings.pythonPath, simulate=simulate)

        if use_tray and not self.offline:
            self._start_tray()

    # ------------------------------------------------------------------ plumbing

    def ui(self, fn):
        """Run fn on the tk thread (safe to call from any thread)."""
        self.q.put(fn)

    def _tk_error(self, exc, val, tb):
        Log.write("UI error: " + "".join(traceback.format_exception(exc, val, tb)).strip())

    def _receive_status(self, status, conn):
        # Ignore stale helper reports only during a confirmed native process exit.
        if not self._os_resolve_missing:
            # If Resolve still reports the previous editing page behind its project
            # dialog, use a conservative, same-process native window check as well.
            if not self.simulate and status.in_project and winapi.project_manager_frontmost():
                from dataclasses import replace
                status=replace(status,busy=True)
            self.state.handle(status, conn)

    def _pump(self):
        try:
            for _ in range(64):
                fn = self.q.get_nowait()
                try:
                    fn()
                except Exception:
                    Log.write("queued call failed: " + traceback.format_exc().strip())
        except queue.Empty:
            pass
        self.root.after(200, self._pump)

    def _tick(self):
        try:
            if self.with_resolve and self._watch_resolve(): return
            if not self.with_resolve and not self.simulate and not self.offline:
                running = winapi.resolve_process_running()
                self._os_resolve_missing = running is False
                if self._os_resolve_missing and (self.state.status.running or self.state.current is not None):
                    self.state.resolve_exited()
            self.state.tick()
        except Exception:
            Log.write("tick failed: " + traceback.format_exc().strip())
        try:
            if os.path.exists(self.open_flag):
                try:
                    os.remove(self.open_flag)
                except OSError:
                    pass
                self.popup.show()
            self._refresh_tray()
            if self.popup.visible:
                self.popup.refresh()
        except Exception:
            Log.write("refresh failed: " + traceback.format_exc().strip())
        self.root.after(1000, self._tick)

    def _watch_resolve(self):
        """--with-resolve: live and die with DaVinci Resolve."""
        now = time.time()
        st = self.state
        running = winapi.resolve_process_running() if not self.simulate else None
        self._os_resolve_missing = running is False
        if running is None:
            self._start_monitor()
            if st.status.running and st.connection.kind != "resolveNotRunning": running = True
            elif st.probe_reported and st.connection.kind == "resolveNotRunning": running = False
        if running is True:
            self.resolve_seen = True
            self._start_monitor()
            self.resolve_gone_since = None
            return False
        if running is not False: return False
        # Independent process exit: freeze immediately even if API last reported healthy.
        if st.status.running or st.current is not None:
            st.resolve_exited()
        if self.resolve_seen:
            if self.resolve_gone_since is None: self.resolve_gone_since = now
            elif now - self.resolve_gone_since >= self.GONE_GRACE_SEC:
                Log.write("Resolve exited, saving and quitting")
                self.quit(); return True
        elif not self.manual and now - self.started_at >= self.NEVER_STARTED_SEC:
            self.quit(); return True
        return False

    # ------------------------------------------------------------------ tray

    def _start_tray(self):
        try:
            import pystray
        except Exception as e:
            Log.write("pystray unavailable: %r" % e)
            self.open_settings_hint = True
            return

        def click(fn):
            return lambda icon, item: self.ui(fn)

        def open_popup(icon, item):
            self.ui(self.popup.show)

        menu = pystray.Menu(
            pystray.MenuItem(lambda item: tr("Open tracker"), open_popup, default=True),
            pystray.MenuItem(lambda item: self._pause_label(), click(self.state.toggle_pause)),
            pystray.MenuItem(lambda item: tr("History…"), click(self.open_history)),
            pystray.MenuItem(lambda item: tr("Settings…"), click(self.open_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: tr("Quit"), click(self.quit)),
        )
        self.icon = pystray.Icon("ResolveEditTracker", make_icon_image("idle"), "Stintory", menu)

        def tray_main():
            try:
                self.icon.run()
            except Exception:
                Log.write("tray crashed: " + traceback.format_exc().strip())
                self.ui(self._tray_fallback)

        if sys.platform == "darwin":
            try: self.icon.run_detached()
            except Exception:
                self.icon = None
                self._tray_fallback()
        else:
            threading.Thread(target=tray_main, name="tray", daemon=True).start()
        self.root.after(5000, self._check_tray_alive)
        Log.write("tray started")

    def _check_tray_alive(self):
        if self.icon is not None and not getattr(self.icon, "visible", False):
            Log.write("tray icon is not visible after 5 s")
            self._tray_fallback()

    def _tray_fallback(self):
        """No tray icon: never leave the user without a way in."""
        Log.write("tray unavailable, opening the panel instead")
        if not self.popup.visible:
            self.popup.show()

    def _pause_label(self):
        from .models import TRACKING
        return tr("Pause") if self.state.state == TRACKING else tr("Resume")

    def _refresh_tray(self):
        if self.icon is None:
            return
        kind = self.state.icon_kind
        if kind != self._last_kind:
            self.icon.icon = make_icon_image(kind)
            self._last_kind = kind
        title = self.state.tray_tooltip
        if title != self._last_title:
            self.icon.title = title
            self._last_title = title
        label = self._pause_label()
        if label != self._last_pause_label:
            self._last_pause_label = label
            try:
                self.icon.update_menu()
            except Exception:
                pass

    # ------------------------------------------------------------------ windows

    def hide_window(self):
        """Keep tracking in the tray; never strand the UI without a tray icon."""
        if self.offline or (self.manual and self.with_resolve and not self.resolve_seen
                            and not self.state.status.running
                            and winapi.resolve_process_running() is not True):
            self.quit()
        elif self.icon is not None and getattr(self.icon, "visible", False):
            self.popup.hide()
        else:
            self.popup.minimize()

    def _start_monitor(self):
        if not self.offline and not self._monitor_started:
            self.monitor.start()
            self._monitor_started = True

    def _schedule_language_refresh(self):
        # Defer destruction of the active combobox until its event returns.
        if self._language_job is None:
            self._language_job = self.root.after_idle(self._refresh_language)

    def _refresh_language(self):
        self._language_job = None
        if self._quitting: return
        self.popup.relocalize()
        # Reopen only existing non-modal windows. Billing/session state and the
        # monitor are never recreated. Modal editors cannot change preferences.
        for window in (self.history_win, self.settings_win):
            if window.win is not None:
                geometry = window.win.geometry()
                visibility = window.win.state()
                window._close(); window.show()
                window.win.geometry(geometry)
                if visibility == "withdrawn": window.win.withdraw()
                elif visibility == "iconic": window.win.iconify()
        self._last_pause_label = None
        self._last_title = None
        self._refresh_tray()

    def open_history(self):
        self.history_win.show()

    def open_settings(self):
        self.settings_win.show()

    # ------------------------------------------------------------------ lifecycle

    def quit(self):
        if self._quitting: return
        self._quitting = True
        try:
            self.state.flush_for_quit()
        finally:
            self.monitor.stop()
            if self.icon is not None:
                try:
                    self.icon.stop()
                except Exception:
                    pass
            for job in self.root.tk.call("after", "info"):
                try: self.root.tk.call("after", "cancel", job)
                except tk.TclError: pass
            self.root.quit()

    def run(self):
        # A manually opened Linked review window does not start the Resolve
        # helper until the native process is detected (unknown platforms fall back).
        if not (self.manual and self.with_resolve and winapi.resolve_process_running() is False):
            self._start_monitor()
        self.root.after(200, self._pump)
        self.root.after(1000, self._tick)
        if not self.background or self.icon is None:
            # Explicit launch opens the dashboard; login stays in the background. open the popup so the app isn't invisible.
            self.root.after(300, lambda: self.popup.show())
        try:
            self.root.mainloop()
        finally:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
