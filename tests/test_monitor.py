import os, sys, tempfile, textwrap, threading, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["RET_DATA_DIR"] = tempfile.mkdtemp()
from resolve_edit_tracker import monitor as mon


class Collect:
    def __init__(self):
        self.items = []
        self.ev = threading.Event()
    def __call__(self, status, conn):
        self.items.append((status, conn))
        self.ev.set()


class MonitorTests(unittest.TestCase):
    def test_simulated_probe_streams_statuses(self):
        c = Collect()
        m = mon.ResolveMonitor(c, simulate=True)
        m.start()
        t0 = time.time()
        while time.time() - t0 < 12 and not any(s.project == "Demo Project" for s, _ in c.items):
            time.sleep(0.2)
        m.stop()
        self.assertTrue(any(s.project == "Demo Project" and conn.kind == "connected" for s, conn in c.items))
        self.assertTrue(any(not s.project for s, _ in c.items))     # Project Manager phase came first

    def test_bad_python_path_is_reported(self):
        c = Collect()
        m = mon.ResolveMonitor(c, python_path="/nope/python.exe")
        m.start()
        self.assertTrue(c.ev.wait(5))
        m.stop()
        self.assertEqual(c.items[0][1].kind, "probeUnavailable")
        self.assertIn("not found", c.items[0][1].detail)

    def test_crashing_probe_gets_restarted_then_reported(self):
        crash = os.path.join(tempfile.mkdtemp(), "crash.py")
        open(crash, "w").write("import sys; sys.stderr.write('boom\\n'); sys.exit(3)\n")
        old = mon.PROBE_PATH
        mon.PROBE_PATH = crash
        try:
            c = Collect()
            m = mon.ResolveMonitor(c, python_path=sys.executable)
            m.start()
            t0 = time.time()
            while time.time() - t0 < 25 and not any(conn.kind == "probeUnavailable" and "keeps quitting" in (conn.detail or "") for _, conn in c.items):
                time.sleep(0.3)
            m.stop()
        finally:
            mon.PROBE_PATH = old
        self.assertTrue(any(conn.kind == "probeUnavailable" and "keeps quitting" in (conn.detail or "")
                            for _, conn in c.items))

    def test_api_down_and_transient_errors(self):
        fake = os.path.join(tempfile.mkdtemp(), "fake.py")
        open(fake, "w").write(textwrap.dedent('''
            import sys, time, json
            lines = [{"running": True, "apiOk": False, "reason": "scripting not responding"},
                     {"running": True, "apiOk": True, "transientError": "x"},
                     {"running": False}]
            for l in lines:
                print(json.dumps(l)); sys.stdout.flush(); time.sleep(0.3)
            time.sleep(30)
        '''))
        old = mon.PROBE_PATH
        mon.PROBE_PATH = fake
        try:
            c = Collect()
            m = mon.ResolveMonitor(c, python_path=sys.executable)
            m.start()
            time.sleep(2.5)
            m.stop()
        finally:
            mon.PROBE_PATH = old
        kinds = [conn.kind for _, conn in c.items]
        self.assertEqual(kinds, ["apiUnavailable", "apiUnavailable", "resolveNotRunning"])  # transient disconnect freezes billing
        self.assertEqual(c.items[0][1].detail, "scripting not responding")


if __name__ == "__main__":
    unittest.main(verbosity=2)
