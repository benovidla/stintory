import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker import __main__ as entry

class ManualTrayTests(unittest.TestCase):
    def app(self):
        a=TrackerApp.__new__(TrackerApp)
        a.manual=True; a.with_resolve=True; a.offline=False; a.resolve_seen=False
        a.state=SimpleNamespace(status=SimpleNamespace(running=False),current=None,connection=SimpleNamespace(kind='resolveNotRunning'),probe_reported=False,resolve_exited=Mock())
        a.icon=SimpleNamespace(visible=True); a.popup=Mock(); a.quit=Mock(); a.monitor=Mock(); a._monitor_started=False
        a.simulate=False; a.started_at=0; a.resolve_gone_since=None
        return a
    def test_manual_wait_no_timeout_then_attach_and_exit(self):
        a=self.app()
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=False):
            self.assertFalse(a._watch_resolve()); a.quit.assert_not_called(); a.monitor.start.assert_not_called()
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=True):
            self.assertFalse(a._watch_resolve()); self.assertFalse(a._watch_resolve())
        a.monitor.start.assert_called_once(); self.assertTrue(a.resolve_seen)
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=False),patch('resolve_edit_tracker.app.time.time',side_effect=[100,103]):
            self.assertFalse(a._watch_resolve()); self.assertTrue(a._watch_resolve())
        a.quit.assert_called_once()
    def test_hide_to_tray_does_not_stop_tracking(self):
        a=self.app(); a.resolve_seen=True; a.hide_window(); a.popup.hide.assert_called_once(); a.quit.assert_not_called()
    def test_no_tray_falls_back_to_taskbar(self):
        a=self.app(); a.resolve_seen=True; a.icon.visible=False; a.hide_window(); a.popup.minimize.assert_called_once(); a.popup.hide.assert_not_called()
    def test_close_manual_without_resolve_exits(self):
        a=self.app()
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=False): a.hide_window()
        a.quit.assert_called_once(); a.popup.hide.assert_not_called()
    def test_resolve_start_race_keeps_app(self):
        a=self.app()
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=True): a.hide_window()
        a.popup.hide.assert_called_once(); a.quit.assert_not_called()
    def test_resident_hides_without_resolve(self):
        a=self.app(); a.with_resolve=False; a.hide_window(); a.popup.hide.assert_called_once(); a.quit.assert_not_called()
    def test_manual_entry_starts_without_resolve(self):
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=False),patch('resolve_edit_tracker.winapi.acquire_single_instance',return_value=True),patch('resolve_edit_tracker.app.TrackerApp') as cls:
            entry.main(['--manual','--with-resolve']); self.assertTrue(cls.call_args.kwargs['manual']); self.assertTrue(cls.call_args.kwargs['with_resolve']); cls.return_value.run.assert_called_once()
    def test_scheduled_remains_noop_without_resolve(self):
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=False),patch('resolve_edit_tracker.app.TrackerApp') as cls:
            entry.main(['--scheduled','--with-resolve']); cls.assert_not_called()
    def test_monitor_starts_at_most_once(self):
        a=self.app(); a._start_monitor(); a._start_monitor(); a.monitor.start.assert_called_once()
