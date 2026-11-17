import os, sys, tempfile, textwrap, time, unittest
os.environ["RET_DATA_DIR"] = tempfile.mkdtemp()
os.environ["RET_SIGNAL_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from resolve_edit_tracker import monitor as mon
from resolve_edit_tracker.app import TrackerApp
from unittest.mock import patch


def fake_probe(lines_before, lines_after):
    path = os.path.join(tempfile.mkdtemp(), "fake.py")
    open(path, "w").write(textwrap.dedent('''
        import json, sys, time
        def e(o): print(json.dumps(o)); sys.stdout.flush()
        for _ in range(%d):
            e({"running": True, "apiOk": True, "page": "edit", "project": "P", "timeline": "T"}); time.sleep(0.5)
        while True:
            e(%s); time.sleep(0.5)
    ''' % (lines_before, lines_after)))
    return path


class WithResolve(unittest.TestCase):
    def run_app(self, probe_src, seconds):
        old = mon.PROBE_PATH
        mon.PROBE_PATH = probe_src
        try:
            app = TrackerApp(use_tray=False, with_resolve=True)
            app.GONE_GRACE_SEC = 3
            app.NEVER_STARTED_SEC = 4
            app.monitor._python_path = sys.executable
            app.root.after(int(seconds * 1000), lambda: setattr(app, "_timeout", True) or app.quit())
            app._timeout = False
            t0 = time.time()
            with patch("resolve_edit_tracker.winapi.resolve_process_running",return_value=None):
                app.run()
            return app, time.time() - t0
        finally:
            mon.PROBE_PATH = old

    def test_quits_after_resolve_closes(self):
        app, took = self.run_app(fake_probe(6, '{"running": False}'), 30)
        self.assertFalse(app._timeout, "app did not quit by itself")
        self.assertTrue(app.resolve_seen)
        self.assertLess(took, 15)

    def test_quits_when_resolve_never_shows_up(self):
        app, took = self.run_app(fake_probe(0, '{"running": False}'), 30)
        self.assertFalse(app._timeout, "app did not quit by itself")
        self.assertFalse(app.resolve_seen)

if __name__ == "__main__":
    unittest.main(verbosity=2)
