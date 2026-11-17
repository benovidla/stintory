import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resolve_edit_tracker import models, csvio, fmt, timesheet
from resolve_edit_tracker.state import AppState
from resolve_edit_tracker.store import SessionStore
from resolve_edit_tracker.models import ResolveStatus, Session


class World:
    """Fake clock + fake Windows + fake probe feed driving a real AppState."""
    def __init__(self, tmp=None, **settings):
        self.tmp = tmp or tempfile.mkdtemp()
        self.t = 1_800_000_000.0
        self.idle = 0.0
        self.fg = (111, "resolve.exe")
        self.toasts = []
        self.status = ResolveStatus(running=True, api_ok=True, page="edit", project="Proj A",
                                    timeline="TL1", timecode="01:00:00:00")
        self.conn = models.CONNECTED
        self.app = AppState(store=SessionStore(self.tmp), clock=lambda: self.t,
                            idle_fn=lambda: self.idle, foreground_fn=lambda: self.fg,
                            toast_fn=lambda **kw: self.toasts.append(kw),
                            autostart_get=lambda: False, autostart_set=lambda e, c: e, own_pid=999)
        if settings:
            self.app.update_settings(**settings)
        self.since_poll = 99

    def step(self, n=1, idle_follows=False, playhead=False):
        for _ in range(n):
            self.t += 1
            if idle_follows:
                self.idle += 1
            if playhead:
                self.status.timecode = "01:00:%02d:00" % (int(self.t) % 60)
            self.since_poll += 1
            if self.since_poll >= 2:
                self.since_poll = 0
                self.app.handle(self.status, self.conn)
            self.app.tick()

    def drop_resolve(self):
        self.status = ResolveStatus(running=False)
        self.conn = models.RESOLVE_NOT_RUNNING


class StateTests(unittest.TestCase):
    def test_auto_start_after_grace_and_toast(self):
        w = World()
        w.step(3)
        self.assertEqual(w.app.state, "notInProject")
        w.step(5)
        self.assertEqual(w.app.state, "tracking")
        self.assertEqual(w.toasts[0]["title"], "Tracking started")
        self.assertEqual(w.toasts[0]["subtitle"], "Proj A")

    def test_untitled_flicker_does_not_start(self):
        w = World()
        w.status.project = "Untitled Project"
        w.step(3)
        w.status.project = "Proj A"
        w.step(3)
        w.status.project = "Untitled Project"
        w.step(3)
        w.status.project = "Proj A"
        w.step(3)
        self.assertEqual(w.app.state, "notInProject")
        w.step(6)
        self.assertEqual(w.app.state, "tracking")

    def test_page_and_timeline_attribution(self):
        w = World()
        w.step(8)
        w.step(60)
        w.status.page = "color"
        w.step(30)
        w.app.toggle_pause()
        s = w.app.sessions[-1]
        self.assertAlmostEqual(s.page_seconds["edit"] + s.page_seconds["color"], s.duration_sec, 3)
        self.assertGreater(s.page_seconds["color"], 25)
        self.assertGreater(s.page_seconds["edit"], 55)
        self.assertEqual(list(s.timeline_seconds), ["TL1"])
        self.assertEqual(s.rate, 25.0)

    def test_away_freezes_then_saves_then_resumes(self):
        w = World()
        w.step(8)
        w.step(30)
        before = w.app.elapsed
        w.fg = (222, "chrome.exe")
        w.step(60)
        self.assertEqual(w.app.state, "tracking")
        self.assertAlmostEqual(w.app.elapsed, before, delta=2)       # frozen
        w.step(40)
        self.assertEqual(w.app.state, "idlePaused")
        self.assertEqual(w.app.idle_pause_reason, "away")
        self.assertIn("switched away", w.app.sessions[-1].note)
        w.fg = (111, "resolve.exe")
        w.step(2)
        self.assertEqual(w.app.state, "tracking")
        self.assertEqual(len(w.toasts), 1)                           # resume is silent by default

    def test_own_window_does_not_count_as_leaving_resolve(self):
        w = World()
        w.step(8)
        w.fg = (999, "python.exe")
        w.step(120)
        self.assertEqual(w.app.state, "tracking")
        self.assertGreater(w.app.elapsed, 100)

    def test_idle_stop_and_resume(self):
        w = World(idleMinutes=3)
        w.step(8)
        w.step(20)
        w.idle = 0
        w.step(185, idle_follows=True)
        self.assertEqual(w.app.state, "idlePaused")
        self.assertIn("idle", w.app.sessions[-1].note)
        w.idle = 0.5
        w.step(2)
        self.assertEqual(w.app.state, "tracking")

    def test_playback_defers_idle_until_hard_limit(self):
        w = World()
        w.step(8)
        w.step(15 * 60, idle_follows=True, playhead=True)
        self.assertEqual(w.app.state, "tracking")
        w.step(20 * 60, idle_follows=True, playhead=True)
        self.assertEqual(w.app.state, "idlePaused")

    def test_render_exempt_from_idle(self):
        w = World()
        w.step(8)
        w.status.rendering = True
        w.step(10 * 60, idle_follows=True)
        self.assertEqual(w.app.state, "tracking")

    def test_project_switch(self):
        w = World()
        w.step(8)
        w.step(20)
        w.status.project = "Proj B"
        w.step(10)
        self.assertEqual(w.app.active_project, "Proj B")
        self.assertEqual(w.app.sessions[-1].project, "Proj A")
        self.assertIn("switched project", w.app.sessions[-1].note)

    def test_switch_does_not_charge_new_timeline_to_old_project(self):
        w = World()
        w.step(8)
        w.step(20)
        w.status.project = "Proj B"
        w.status.timeline = "TL2"
        w.step(10)
        self.assertNotIn("TL2", w.app.sessions[-1].timeline_seconds)
        self.assertIn("TL2", w.app.current.timeline_seconds)

    def test_switch_timeline_in_same_project(self):
        w = World()
        w.step(8)
        w.step(20)
        w.status.timeline = "TL2"
        w.step(15)
        w.app.toggle_pause()
        s = w.app.sessions[-1]
        self.assertGreater(s.timeline_seconds["TL1"], 15)
        self.assertGreater(s.timeline_seconds["TL2"], 10)
        self.assertAlmostEqual(sum(s.timeline_seconds.values()), s.duration_sec)

    def test_project_close_freezes_and_saves_quickly(self):
        w=World(); w.step(30); before=w.app.elapsed
        w.status.project=None; w.status.timeline=None; w.status.page=None
        w.step(2); frozen=w.app.elapsed
        self.assertLessEqual(frozen,before+1)
        w.step(6)
        self.assertEqual(w.app.state,"notInProject")
        self.assertIsNone(w.app.active_project)
        self.assertAlmostEqual(w.app.sessions[-1].duration_sec,frozen,delta=1)
        w.status.project="Proj B";w.status.timeline="TL2";w.status.page="edit";w.step(8)
        self.assertEqual(w.app.active_project,"Proj B")

    def test_confirmed_process_exit_immediately_saves_once(self):
        w=World();w.step(30);before=w.app.elapsed
        w.app.resolve_exited();w.app.resolve_exited();w.app.flush_for_quit()
        self.assertEqual(w.app.state,"notInProject")
        self.assertEqual(len(w.app.sessions),1)
        self.assertEqual(w.app.sessions[0].duration_sec,before)
        self.assertIn("Resolve quit",w.app.sessions[0].note)

    def test_connection_loss_with_stale_project_stops_without_billing(self):
        w=World(); w.step(30); before=w.app.elapsed
        w.conn=models.probe_unavailable("helper stopped"); w.step(15)
        self.assertEqual(w.app.state,"notInProject")
        self.assertIsNone(w.app.active_project)
        self.assertLessEqual(w.app.sessions[-1].duration_sec,before+1)
        w.conn=models.CONNECTED; w.step(8)
        self.assertEqual(w.app.state,"tracking")

    def test_resolve_quit_saves_session(self):
        w = World()
        w.step(8)
        w.step(30)
        w.drop_resolve()
        w.step(8)
        self.assertEqual(w.app.state, "notInProject")
        self.assertIn("Resolve quit", w.app.sessions[-1].note)

    def test_project_manager_freezes_and_resumes(self):
        w = World(idleMinutes=0)
        w.step(30); before = w.app.elapsed
        w.status.page = None; w.status.busy = True
        w.step(300, playhead=True)
        self.assertFalse(w.app.is_actively_tracking)
        self.assertEqual(w.app.icon_kind, "paused")
        self.assertLessEqual(w.app.elapsed, before + 1)
        frozen = w.app.elapsed
        w.status.page = "edit"; w.status.busy = False
        w.step(10)
        self.assertTrue(w.app.is_actively_tracking)
        self.assertGreater(w.app.elapsed, frozen + 6)
        self.assertEqual(w.app.active_project, "Proj A")

    def test_project_manager_cannot_resume_manual_pause(self):
        w=World(); w.step(30); w.app.toggle_pause()
        w.status.page=None; w.status.busy=True; w.step(40)
        w.app.toggle_pause()
        self.assertIsNone(w.app.current)
        self.assertEqual(w.app.state,"manuallyPaused")

    def test_project_manager_cannot_resume_idle_pause(self):
        w=World(); w.step(30); w.app.state="idlePaused"; w.app._end_session("idle")
        w.status.page=None; w.step(20)
        self.assertIsNone(w.app.current)
        w.status.page="edit"; w.step(4)
        self.assertTrue(w.app.is_actively_tracking)

    def test_project_manager_before_first_project_does_not_start(self):
        w=World(); w.status.page=None; w.status.busy=True; w.step(60)
        self.assertIsNone(w.app.current)
        w.status.page="edit"; w.status.busy=False; w.step(10)
        self.assertTrue(w.app.is_actively_tracking)

    def test_switch_project_from_manager_keeps_attribution(self):
        w=World(); w.step(30); before=w.app.elapsed
        w.status.page=None; w.status.busy=True; w.step(20)
        w.status.project="Proj B"; w.status.timeline="TL2"; w.status.page="edit"; w.status.busy=False
        w.step(15)
        self.assertEqual(w.app.active_project,"Proj B")
        self.assertLessEqual(w.app.sessions[-1].duration_sec,before+1)
        self.assertNotIn("TL2",w.app.sessions[-1].timeline_seconds)
        self.assertIn("TL2",w.app.current.timeline_seconds)

    def test_long_manager_pause_saves_and_does_not_restart(self):
        w=World(idleMinutes=0); w.step(30); before=w.app.elapsed
        w.status.page=None; w.step(930)
        self.assertEqual(w.app.state,"idlePaused")
        self.assertIsNone(w.app.current)
        self.assertLessEqual(w.app.sessions[-1].duration_sec,before+1)
        w.step(30); self.assertIsNone(w.app.current)

    def test_off_page_render_does_not_override_pause(self):
        w=World(); w.step(30); before=w.app.elapsed
        w.status.page=None; w.status.rendering=True; w.step(30)
        self.assertLessEqual(w.app.elapsed,before+1)

    def test_sleep_gap_ends_session_at_last_tick(self):
        w = World()
        w.step(8)
        w.step(30)
        slept_from = w.t
        w.t += 3600
        w.app.tick()
        s = w.app.sessions[-1]
        self.assertIn("PC sleep", s.note)
        self.assertAlmostEqual(s.end, slept_from, delta=1)
        self.assertLess(s.duration_sec, 60)

    def test_manual_pause_and_auto_resume(self):
        w = World()
        w.step(8)
        w.step(10)
        w.app.toggle_pause()
        self.assertEqual(w.app.state, "manuallyPaused")
        w.step(10)
        self.assertEqual(w.app.state, "manuallyPaused")
        w.step(15)
        self.assertEqual(w.app.state, "tracking")

    def test_toggle_file(self):
        w = World()
        w.step(8)
        open(w.app.toggle_file, "w").close()
        w.step(1)
        self.assertEqual(w.app.state, "manuallyPaused")
        self.assertFalse(os.path.exists(w.app.toggle_file))

    def test_crash_recovery(self):
        w = World()
        w.step(8)
        w.step(45)
        w.app.store.save_current(w.app.current)            # what the 20 s checkpoint does
        w2 = World(tmp=w.tmp)
        self.assertEqual(len(w2.app.sessions), 1)
        self.assertIn("(recovered)", w2.app.sessions[0].note)
        self.assertGreater(w2.app.sessions[0].duration_sec, 40)
        self.assertFalse(os.path.exists(w2.app.store.current_path))

    def test_gated_start_when_resolve_not_frontmost(self):
        w = World()
        w.fg = (222, "chrome.exe")
        w.step(10)
        self.assertEqual(w.app.state, "idlePaused")
        w.fg = (111, "resolve.exe")
        w.step(2)
        self.assertEqual(w.app.state, "tracking")
        self.assertEqual(w.toasts[0]["title"], "Tracking started")  # fresh, not resume

    def test_frontmost_gate_can_be_turned_off(self):
        w = World(trackOnlyWhenFrontmost=False)
        w.fg = (222, "chrome.exe")
        w.step(10)
        w.step(120)
        self.assertEqual(w.app.state, "tracking")
        self.assertGreater(w.app.elapsed, 100)

    def test_rates_stored_per_session(self):
        w = World(projectRates={"Proj A": 40.0})
        w.step(8)
        w.step(3600 // 10)
        w.app.toggle_pause()
        s = w.app.sessions[-1]
        self.assertEqual(s.rate, 40.0)
        w.app.update_settings(rate=99.0, projectRates={})
        self.assertEqual(w.app.sessions[-1].rate, 40.0)             # history never rewritten

    def test_stats(self):
        w = World()
        w.step(8)
        w.step(120)
        st = w.app.stats
        self.assertGreater(st.today_sec, 100)
        self.assertGreater(st.week_sec, 100)
        self.assertEqual(st.breakdown[0][0], "edit")


class DataTests(unittest.TestCase):
    def test_reads_swift_sessions_json(self):
        d = tempfile.mkdtemp()
        swift = [{
            "id": "6F1B5E0E-1111-4A8D-9E57-AAAAAAAAAAAA", "project": "Wedding", "start": "2026-08-31T19:20:00Z",
            "end": "2026-08-31T20:20:00Z", "durationSec": 3600, "rate": 30, "currency": "€",
            "note": "(paused)", "pageSeconds": {"edit": 3000, "color": 600}, "timelineSeconds": {"Main": 3600}}]
        json.dump(swift, open(os.path.join(d, "sessions.json"), "w"))
        st = SessionStore(d)
        s = st.sessions[0]
        self.assertEqual(s.project, "Wedding")
        self.assertAlmostEqual(s.earnings, 30.0)
        st.append(Session(project="X", start=s.start + 10, end=s.start + 20, duration_sec=10, rate=1, currency="€"))
        again = json.load(open(os.path.join(d, "sessions.json")))
        self.assertEqual(again[0]["start"], "2026-08-31T19:20:00Z")
        self.assertEqual(again[0]["pageSeconds"], {"color": 600.0, "edit": 3000.0})

    def test_settings_tolerant(self):
        s = models.Settings.from_json({"rate": "30", "idleMinutes": 7, "bogus": 1, "soundName": None})
        self.assertEqual(s.rate, 30.0)
        self.assertEqual(s.idleMinutes, 7)
        self.assertEqual(s.currency, "€")

    def test_csv_roundtrip(self):
        s1 = Session(project="P", start=fmt.parse_session_date("2026-03-01 10:15"), end=0,
                     duration_sec=5025, rate=30, currency="€", note='He said "hi", ok')
        s1.end = s1.start + s1.duration_sec
        text = csvio.export_csv([s1])
        self.assertTrue(text.startswith("Date,Duration,Earnings,Note\n"))
        self.assertIn("2026-03-01 10:15,1:23:45,€41.88,", text)
        back = csvio.import_csv("\ufeff" + text, "€")
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0].note, 'He said "hi", ok')
        self.assertAlmostEqual(back[0].duration_sec, 5025)
        self.assertAlmostEqual(back[0].earnings, 41.88, places=1)

    def test_money_format(self):
        self.assertEqual(fmt.money(5, "€"), "€5.00")
        self.assertEqual(fmt.money(5, "Kč"), "5.00 Kč")
        self.assertEqual(fmt.hms(3725), "1:02:05")

    def test_timesheet_html(self):
        from datetime import date
        s = Session(project="A <b>", start=fmt.parse_session_date("2026-03-01 10:00"), end=0,
                    duration_sec=7200, rate=25, currency="€", note="x & y",
                    page_seconds={"edit": 7200}, timeline_seconds={"TL": 7200})
        s.end = s.start + 7200
        html = timesheet.build_html([s], timesheet.ReportRange(None, date(2026, 3, 1), date(2026, 3, 31)), "€")
        self.assertIn("A &lt;b&gt;", html)
        self.assertIn("2.00 h", html)
        self.assertIn("€50.00", html)
        self.assertIn("x &amp; y", html)
        empty = timesheet.build_html([s], timesheet.ReportRange("Nope", date(2026, 3, 1), date(2026, 3, 31)), "€")
        self.assertIn("No sessions in this range", empty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
