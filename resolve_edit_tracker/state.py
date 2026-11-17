"""Tracker state machine: start / stop / idle / away logic, session bookkeeping, stats.

A direct port of AppState.swift. Everything here runs on the UI thread: the monitor's
worker thread hands statuses over through the UI queue, so no locking is needed.
Clock, idle source and foreground-window source are injectable for testing.
"""

from .i18n import tr
import dataclasses
import math
import os
import time

from . import csvio, fmt, models, winapi
from .models import (IDLE_PAUSED, MANUALLY_PAUSED, NOT_IN_PROJECT, TRACKING, ResolveStatus,
                     Session, Settings, page_display)
from .store import SessionStore
from .util import Log, read_json, write_json_atomic

# Timings (seconds), same values as the macOS app.
MAX_BUSY_SEC = 15 * 60          # stop if Resolve stays off-page this long while tracking
MANUAL_RESUME_AFTER_SEC = 20
START_GRACE = 4
SWITCH_GRACE = 6
AWAY_GRACE_SEC = 90
HARD_IDLE_SEC = 30 * 60
SLEEP_GAP_SEC = 30              # a tick gap this big means the PC slept (or the app was frozen)

FRESH, RESUME, PROJECT_SWITCH = "fresh", "resume", "projectSwitch"
RESOLVE_EXE = "resolve.exe"


class AppState:
    def __init__(self, store=None, clock=time.time, idle_fn=winapi.idle_seconds,
                 foreground_fn=winapi.foreground_info, toast_fn=None,
                 launch_command="", autostart_get=winapi.autostart_enabled,
                 autostart_set=winapi.autostart_set, own_pid=None):
        self.clock = clock
        self.idle_fn = idle_fn
        self.foreground_fn = foreground_fn
        self.toast_fn = toast_fn or (lambda **kw: None)
        self.launch_command = launch_command
        self._autostart_set = autostart_set
        self.own_pid = own_pid if own_pid is not None else os.getpid()

        self.store = store or SessionStore()
        self.settings_path = self.store.settings_path
        self.settings = Settings.from_json(read_json(self.settings_path))

        # published state
        self.state = NOT_IN_PROJECT
        self.status = models.OFFLINE
        self.connection = models.RESOLVE_NOT_RUNNING
        self.stats = models.Stats()
        self.elapsed = 0.0
        self.note_draft = ""

        # internals
        self.current = None
        self.active_project = None
        self.last_tick = clock()
        self.tick_count = 0
        self.last_in_project_at = clock()
        self.last_known_page = "edit"
        self.busy_since = None
        self.announced_project = None
        self.active_while_paused_sec = 0.0
        self.last_stats_at = 0.0
        self.probe_reported = False
        self.pending_project = None
        self.pending_project_since = 0.0
        self.away_since = None
        self.last_resolve_frontmost = True
        self.last_timecode = None
        self.timecode_moved_at = 0.0
        self.zero_input_since = None
        self.idle_pause_reason = "idle"                # "idle" | "away"
        self.toggle_file = os.path.join(self.store.directory, "toggle.pause")

        Log.write("— launch —")
        self._recover_crashed_session()
        self._rebuild_stats(force=True)
        self.settings.launchAtLogin = autostart_get()

    # ------------------------------------------------------------------ presence

    @staticmethod
    def _presence(s):
        if not s.running:
            return ("resolveGone", None)
        if not s.api_ok:
            return ("apiDown", None)
        if not s.project:
            return ("noProject", None)
        return ("busy", s.project) if not s.in_project else ("editing", s.project)

    @staticmethod
    def _stop_grace(kind):
        return {"resolveGone": 4, "apiDown": 10, "noProject": 4}.get(kind, float("inf"))

    @property
    def store_directory(self):
        return self.store.directory

    @property
    def sessions(self):
        return self.store.sessions

    @property
    def project_names(self):
        names = {s.project for s in self.store.sessions}
        if self.status.project:
            names.add(self.status.project)
        if self.active_project:
            names.add(self.active_project)
        return sorted(names, key=str.lower)

    # ------------------------------------------------------------------ crash recovery / sleep

    def _recover_crashed_session(self):
        s = self.store.load_current()
        if s is None:
            return
        # Older checkpoints can contain duration without page detail; preserve it.
        s.duration_sec = max(s.duration_sec, sum(s.page_seconds.values()))
        s.end = max(s.end, s.start + s.duration_sec)
        if s.duration_sec >= 1 and not any(x.id == s.id for x in self.store.sessions):
            s.note = " ".join(x for x in ["(recovered)", s.note] if x)
            self.store.append(s)
        self.store.save_current(None)

    def _handle_sleep(self, slept_at):
        if self.current is not None:
            self._end_session("(auto-stopped: PC sleep)", end_time=slept_at)
        if self.state == TRACKING:
            self.state = IDLE_PAUSED
        Log.write("💤 sleep / long gap")

    # ------------------------------------------------------------------ Resolve status handling

    def handle(self, new_status, new_connection):
        self.probe_reported = True
        was_editing = self.status.in_project and self.connection.is_healthy
        self.status = new_status
        # Avoid charging the boundary tick on returning from an off-page dialog.
        if new_status.in_project and new_connection.is_healthy and not was_editing:
            self.last_tick = self.clock()
        self.connection = new_connection
        self._note_timecode(new_status.timecode)
        self._handle_inner(new_status, new_connection)
        self._rebuild_stats()

    def _handle_inner(self, new_status, new_connection):
        now = self.clock()
        kind, project = self._presence(new_status)
        if new_connection.kind in ("apiUnavailable", "probeUnavailable"):
            kind, project = "apiDown", None
        elif new_connection.kind == "resolveNotRunning":
            kind, project = "resolveGone", None
        if kind in ("editing", "busy"):
            self.last_in_project_at = now
        confirmed_out = (now - self.last_in_project_at) >= self._stop_grace(kind)

        if self.state == NOT_IN_PROJECT:
            if kind != "editing":
                self.pending_project = None
                return
            # The name must hold briefly before we start: filters the default
            # "Untitled Project" name Resolve flashes during load / modal tasks.
            if self.pending_project != project:
                self.pending_project = project
                self.pending_project_since = now
                return
            if now - self.pending_project_since < START_GRACE:
                return
            self.pending_project = None

            gated_out = self.settings.trackOnlyWhenFrontmost and not self._is_resolve_frontmost()
            if self._is_idle_beyond_limit() or gated_out:
                self.state = IDLE_PAUSED
                self.idle_pause_reason = "away" if gated_out else "idle"
                self.active_project = project
                self.announced_project = None
                Log.write("• project open, waiting: %s (%s)" % (
                    "not in Resolve" if gated_out else "idle", project))
            else:
                self._enter_tracking(project, FRESH)

        elif self.state == TRACKING:
            if kind == "editing":
                if project == self.active_project:
                    self.pending_project = None
                elif self.pending_project != project:
                    self.pending_project = project
                    self.pending_project_since = now
                elif now - self.pending_project_since >= SWITCH_GRACE:
                    self._end_session("(auto-stopped: switched project)")
                    self._enter_tracking(project, PROJECT_SWITCH)
                    Log.write("⇄ switched project → %s" % project)
            elif kind == "busy":
                self.pending_project = None        # a modal task never accompanies a real switch
            elif confirmed_out:
                note = self._stop_note(new_connection)
                self._end_session(note)
                self.state = NOT_IN_PROJECT
                self.active_project = None
                self.announced_project = None
                self.pending_project = None
                Log.write("⏹ " + note)

        else:   # idle or manually paused
            if kind in ("noProject", "apiDown", "resolveGone") and confirmed_out:
                self.state = NOT_IN_PROJECT
                self.active_project = None
                self.announced_project = None
                self.pending_project = None

    @staticmethod
    def _stop_note(conn):
        return {
            "resolveNotRunning": "(auto-stopped: Resolve quit)",
            "apiUnavailable": "(auto-stopped: lost Resolve connection)",
            "probeUnavailable": "(auto-stopped: tracker helper stopped)",
            "connected": "(auto-stopped: project closed)",
        }[conn.kind]

    def _is_idle_beyond_limit(self):
        if self.settings.idleMinutes <= 0:
            return False
        if self.settings.pauseDuringRenders and self.status.rendering:
            return False
        return self.idle_fn() >= self.settings.idleMinutes * 60

    def _note_timecode(self, tc):
        if not tc or tc == self.last_timecode:
            return
        self.last_timecode = tc
        self.timecode_moved_at = self.clock()

    @property
    def is_playing_back(self):
        """A moving playhead (playback, scrubbing, Speed Editor jog) defeats the idle timer."""
        return self.clock() - self.timecode_moved_at < 5

    def _is_resolve_frontmost(self):
        info = self.foreground_fn()
        if info is None:
            return self.last_resolve_frontmost
        pid, exe = info
        if pid == self.own_pid:                    # our popup / settings window isn't "leaving Resolve"
            return self.last_resolve_frontmost
        self.last_resolve_frontmost = (exe in (RESOLVE_EXE, "resolve"))
        return self.last_resolve_frontmost

    @property
    def tracking_gate_open(self):
        return (not self.settings.trackOnlyWhenFrontmost) or self._is_resolve_frontmost()

    def _enter_tracking(self, project, reason):
        self._begin_session(project)
        self.state = TRACKING
        s = self.settings
        if reason == FRESH:
            Log.write("▶ start tracking: %s" % project)
            self.toast_fn(title=tr("Tracking started"), subtitle=project, kind="record",
                          play_sound=s.playSoundOnStart, sound_name=s.soundName)
        elif reason == RESUME:
            Log.write("▶ resume: %s" % project)
            if s.toastOnIdleResume:
                self.toast_fn(title=tr("Resumed"), subtitle=project, kind="record",
                              play_sound=False, sound_name=s.soundName)
        else:
            self.toast_fn(title=tr("Switched project"), subtitle=project, kind="switch",
                          play_sound=False, sound_name=s.soundName)
        self.announced_project = project

    # ------------------------------------------------------------------ per-second tick

    def tick(self):
        now = self.clock()
        dt = now - self.last_tick
        prev_tick = self.last_tick
        self.last_tick = now

        if dt > SLEEP_GAP_SEC:
            self._handle_sleep(prev_tick)
            dt = 0.0

        self._check_toggle_file()
        idle = self.idle_fn()

        if self.state == TRACKING:
            self._tick_tracking(now, dt, idle)
        elif self.state == IDLE_PAUSED:
            ready = idle < 2 or (self.idle_pause_reason in ("away", "inactive") and not self._is_idle_beyond_limit())
            if ready and self.tracking_gate_open and self.status.in_project and self.connection.is_healthy:
                project = self.status.project
                self._enter_tracking(project, RESUME if self.announced_project == project else FRESH)
        elif self.state == MANUALLY_PAUSED:
            self.elapsed = 0.0
            if self.connection.is_healthy and self.status.in_project and idle < 3 and 0 < dt < 5 and self.tracking_gate_open:
                self.active_while_paused_sec += dt
                if self.active_while_paused_sec >= MANUAL_RESUME_AFTER_SEC:
                    project = self.status.project
                    Log.write("▶ auto-resume from manual pause (kept working)")
                    self._enter_tracking(project, RESUME if self.announced_project == project else FRESH)
                    self.active_while_paused_sec = 0.0
            else:
                self.active_while_paused_sec = 0.0
        else:
            self.elapsed = 0.0

        self.tick_count += 1
        if self.current is not None and self.tick_count % 2 == 0:
            self.store.save_current(self.current)
        self._rebuild_stats()

    def _tick_tracking(self, now, dt, idle):
        if self.status.page_enum:
            self.last_known_page = self.status.page_enum

        # Freeze (don't accrue, don't stop) while the user works in another app.
        # Save the session if they stay away past the grace window.
        if self.settings.trackOnlyWhenFrontmost and not self._is_resolve_frontmost():
            self.busy_since = None
            if self.away_since is None:
                self.away_since = now
            self.elapsed = self.current.duration_sec if self.current else 0.0
            if now - self.away_since >= AWAY_GRACE_SEC:
                self._end_session("(auto-stopped: switched away from Resolve)")
                self.state = IDLE_PAUSED
                self.idle_pause_reason = "away"
                self.elapsed = 0.0
                self.away_since = None
                Log.write("⏸ away from Resolve")
            return
        self.away_since = None

        if not self.status.in_project:
            # The API may retain the old project/timeline behind Project Manager.
            # Never accrue on an unknown page, even with idle disabled or playback.
            if self.busy_since is None:
                self.busy_since = now
                Log.write("Tracking frozen: no active editing page")
            self.elapsed = self.current.duration_sec if self.current else 0.0
            if now - self.busy_since >= MAX_BUSY_SEC:
                self._end_session("(auto-stopped: Resolve inactive)")
                self.state = IDLE_PAUSED
                self.idle_pause_reason = "inactive"
                self.busy_since = None
            return
        self.busy_since = None

        s = self.current
        if (0 < dt < 5 and s is not None and self.connection.is_healthy
                and self.status.in_project and self.status.project == s.project):
            page = self.status.page_enum or self.last_known_page
            s.page_seconds[page] = s.page_seconds.get(page, 0.0) + dt
            tl = self.status.timeline or "—"
            s.timeline_seconds[tl] = s.timeline_seconds.get(tl, 0.0) + dt
            s.duration_sec = sum(s.page_seconds.values())
            s.end = now
        self.elapsed = s.duration_sec if s else 0.0

        if idle < 5:
            self.zero_input_since = None
        elif self.zero_input_since is None:
            self.zero_input_since = now - idle

        # Renders on a known editing page are exempt from idle (if opted in).
        # Playback review defers idle-stop up to a hard ceiling.
        render_hold = self.settings.pauseDuringRenders and self.status.rendering
        soft_hold = self.is_playing_back
        hard_idle = (now - self.zero_input_since >= HARD_IDLE_SEC) if self.zero_input_since else False

        if (self.settings.idleMinutes > 0 and not render_hold
              and idle >= self.settings.idleMinutes * 60 and (not soft_hold or hard_idle)):
            self._end_session("(auto-stopped: idle)")
            self.state = IDLE_PAUSED
            self.idle_pause_reason = "idle"
            self.elapsed = 0.0
            Log.write("⏸ idle pause (idle %ds)" % int(idle))

    def _check_toggle_file(self):
        """`ResolveEditTracker.exe --toggle-pause` drops this file; handy for hotkey tools."""
        if os.path.exists(self.toggle_file):
            try:
                os.remove(self.toggle_file)
            except OSError:
                return
            self.toggle_pause()

    # ------------------------------------------------------------------ session bookkeeping

    def _begin_session(self, project):
        self.active_project = project
        self.busy_since = None
        self.away_since = None
        self.pending_project = None
        self.zero_input_since = None
        now = self.clock()
        self.current = Session(project=project, start=now, end=now, duration_sec=0.0,
                               rate=self.settings.rate_for(project),
                               currency=self.settings.currency, note="")
        self.last_tick = now
        self.store.save_current(self.current)

    def _end_session(self, auto_note, end_time=None):
        s = self.current
        if s is None:
            return
        s.end = end_time if end_time is not None else self.clock()
        s.duration_sec = sum(s.page_seconds.values())
        user = self.note_draft.strip()
        s.note = " ".join(x for x in [user, auto_note] if x)
        if s.duration_sec >= 1:
            self.store.append(s)
        self.current = None
        self.store.save_current(None)
        self.note_draft = ""
        self.elapsed = 0.0
        self._rebuild_stats(force=True)

    # ------------------------------------------------------------------ user actions

    def toggle_pause(self):
        if self.state == TRACKING:
            self._end_session("(paused)")
            self.state = MANUALLY_PAUSED
            self.active_while_paused_sec = 0.0
            Log.write("⏸ manual pause")
        elif self.state in (MANUALLY_PAUSED, IDLE_PAUSED):
            if self.status.in_project and self.connection.is_healthy:
                project = self.status.project
                self._enter_tracking(project, RESUME if self.announced_project == project else FRESH)
        self._rebuild_stats(force=True)

    def resolve_exited(self):
        """A confirmed OS process exit is not an API hiccup; save immediately."""
        self.status = models.OFFLINE
        self.connection = models.RESOLVE_NOT_RUNNING
        self.probe_reported = True
        if self.current is not None:
            self._end_session("(auto-stopped: Resolve quit)")
        self.state = NOT_IN_PROJECT
        self.active_project = None
        self.pending_project = None
        self.announced_project = None
        self.elapsed = 0.0
        self._rebuild_stats(force=True)

    def flush_for_quit(self):
        if self.current is not None:
            self._end_session("(app quit)")
        self.store.save_current(None)

    # ------------------------------------------------------------------ history editing

    def delete_sessions(self, ids):
        self.store.delete(ids)
        self._rebuild_stats(force=True)

    def update_session(self, session):
        s = session
        s.duration_sec = max(0.0, s.duration_sec)
        s.end = s.start + s.duration_sec
        if not s.page_seconds:
            s.page_seconds = {"edit": s.duration_sec}
        self.store.update(s)
        self._rebuild_stats(force=True)

    def add_manual_session(self, project, start, minutes, note, page):
        if not math.isfinite(minutes) or minutes<0: raise ValueError('Invalid session duration')
        dur = minutes * 60.0
        project = project.strip() or "Untitled"
        s = Session(project=project, start=start, end=start + dur, duration_sec=dur,
                    rate=self.settings.rate_for(project), currency=self.settings.currency,
                    note=note, page_seconds={page: dur}, timeline_seconds={}, manual=True)
        self.store.append(s)
        self._rebuild_stats(force=True)
        Log.write("＋ manual entry: %s %dm" % (s.project, int(minutes)))

    def clear_history(self):
        self.store.replace_all([])
        self.announced_project = None
        self._rebuild_stats(force=True)
        Log.write("history cleared")

    def import_sessions(self, text):
        imported = csvio.import_csv(text, self.settings.currency)
        if not imported:
            return 0
        self.store.replace_all(self.store.sessions + imported)
        self._rebuild_stats(force=True)
        return len(imported)

    def export_csv(self):
        return csvio.export_csv(self.store.sessions)

    # ------------------------------------------------------------------ settings

    def update_settings(self, **changes):
        old = self.settings
        from .currencies import billing_changes
        new = Settings.from_json(dataclasses.replace(old, **billing_changes(old, changes)).to_json())
        if new.launchAtLogin:
            new.launchAtLogin = False
        self.settings = new
        try:
            write_json_atomic(self.settings_path, new.to_json())
        except OSError as e:
            Log.write("couldn't save settings: %r" % e)
        self._rebuild_stats(force=True)

    # ------------------------------------------------------------------ derived

    def _rebuild_stats(self, force=False):
        now = self.clock()
        if not force and now - self.last_stats_at < 2:
            return
        self.last_stats_at = now
        self.stats = fmt.build_stats(self.store.sessions, self.current,
                                     self.status.project or self.active_project, now)

    # ------------------------------------------------------------------ tray helpers

    @property
    def icon_kind(self):
        if not self.connection.is_healthy and self.state == NOT_IN_PROJECT \
                and self.connection.kind != "resolveNotRunning":
            return "warning"
        if self.state == TRACKING and not self.is_actively_tracking:
            return "paused"
        return {TRACKING: "tracking", IDLE_PAUSED: "paused", MANUALLY_PAUSED: "paused",
                NOT_IN_PROJECT: "idle"}[self.state]

    @property
    def is_actively_tracking(self):
        return (self.state == TRACKING and self.connection.is_healthy
                and self.status.in_project and self.status.project == self.active_project
                and self.away_since is None)

    @property
    def status_line(self):
        if self.state == TRACKING:
            if not self.connection.is_healthy: return self.connection.short_label
            if not self.status.has_project: return tr("Resolve open · no project")
            if not self.status.in_project or self.status.project != self.active_project:
                return tr("Paused")
            if self.status.rendering:
                return tr("Tracking · Rendering")
            return tr("Tracking · %s") % (page_display(self.status.page_enum) if self.status.page_enum
                                      else (self.status.page or "—"))
        if self.state == IDLE_PAUSED:
            return tr("Paused · switch to Resolve") if self.idle_pause_reason == "away" else tr("Paused (idle)")
        if self.state == MANUALLY_PAUSED:
            return tr("Paused")
        k = self.connection.kind
        if k == "connected":
            return tr("Resolve open · no project")
        return self.connection.short_label

    @property
    def tray_tooltip(self):
        name = self.status.project or self.stats.project or "Stintory"
        parts = [name, self.status_line]
        if self.settings.menuBarShowTime and self.state == TRACKING:
            parts.append(fmt.hms(self.elapsed))
        return " · ".join(parts)[:120]
