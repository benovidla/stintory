"""Runs the probe as a child process, turns its stdout into ResolveStatus values and keeps
an overall ConnectionState. Restarts the probe if it dies or goes quiet."""
import json
import os
import subprocess
import sys
import threading
import time

from . import models
from .models import ResolveStatus
from .util import Log

PROBE_PATH = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "probe.py")
if getattr(sys, "frozen", False) and not os.path.exists(PROBE_PATH):
    PROBE_PATH = os.path.join(getattr(sys, "_MEIPASS", ""), "resolve_edit_tracker", "probe.py")


class ResolveMonitor:
    def __init__(self, on_update, python_path="", simulate=False):
        self._on_update = on_update              # called from a worker thread
        self._python_path = python_path
        self._simulate = simulate
        self._stopped = threading.Event()
        self._proc = None
        self._thread = None
        self._last_good = 0.0
        self._failures = 0
        self._last_status = models.OFFLINE
        self._reported_capabilities = None

    # ---------------------------------------------------------------- lifecycle

    def start(self):
        self._thread = threading.Thread(target=self._supervise, name="resolve-monitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stopped.set()
        # Detach callbacks before workers exit so they cannot retain or call Tk objects.
        self._on_update = None
        p = self._proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout=4.0)

    # ---------------------------------------------------------------- command

    def _command(self):
        args = ["--simulate"] if self._simulate else []
        if self._python_path:
            if os.path.isfile(self._python_path):
                return [self._python_path, "-u", PROBE_PATH] + args, None
            return None, "Python interpreter not found at %s" % self._python_path
        if getattr(sys, "frozen", False):
            # A separate console-enabled helper is used on Windows: windowed PyInstaller apps lack stdout.
            if sys.platform == "win32":
                helper=os.path.join(os.path.dirname(sys.executable), "StintoryProbe.exe")
                if os.path.isfile(helper): return [helper]+args,None
            return [sys.executable, "--probe"] + args, None
        exe = sys.executable
        if os.path.basename(exe).lower() == "pythonw.exe":
            cand = os.path.join(os.path.dirname(exe), "python.exe")
            if os.path.exists(cand):
                exe = cand
        return [exe, "-u", PROBE_PATH] + args, None

    # ---------------------------------------------------------------- supervisor

    def _supervise(self):
        while not self._stopped.is_set():
            cmd, err = self._command()
            if cmd is None:
                self._report(models.probe_unavailable(err))
                self._stopped.wait(15)
                continue
            try:
                env = dict(os.environ)
                env["STINTORY_PARENT_PID"] = str(os.getpid())
                env.pop("PYTHONPATH", None)
                env.pop("PYTHONHOME", None)        # a wrong PYTHONHOME makes python die at startup
                self._proc = subprocess.Popen(
                    cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0,
                    bufsize=0)
            except OSError as e:
                self._failures += 1
                self._report(models.probe_unavailable("couldn't start python (%s)" % e))
                self._stopped.wait(10)
                continue

            proc = self._proc
            self._last_good = time.time()
            got_line = threading.Event()
            readers=[threading.Thread(target=self._read_stdout, args=(proc, got_line), daemon=True), threading.Thread(target=self._read_stderr, args=(proc,), daemon=True)]
            for reader in readers: reader.start()

            while not self._stopped.is_set() and proc.poll() is None:
                self._stopped.wait(1.0)
                if time.time() - self._last_good > 12:
                    self._report(models.probe_unavailable("no response from the tracker helper, restarting"))
                    Log.write("probe silent for 12s, restarting")
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    break

            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=1)
            for reader in readers: reader.join(timeout=0.5)
            for pipe in (proc.stdout,proc.stderr):
                if pipe is not None: pipe.close()
            if self._stopped.is_set():
                break
            self._report(models.probe_unavailable("Resolve helper disconnected; reconnecting"))
            if not got_line.is_set():
                self._failures += 1
                if self._failures >= 4:
                    self._report(models.probe_unavailable("the tracker helper keeps quitting unexpectedly (see debug.log)"))
            self._stopped.wait(3)

    def _read_stdout(self, proc, got_line):
        buf = b""
        while True:
            chunk = proc.stdout.read(4096) if proc.stdout else b""
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    status = ResolveStatus.from_dict(json.loads(line.decode("utf-8", "replace")))
                except (ValueError, AttributeError):
                    continue
                got_line.set()
                self._failures = 0
                self._last_good = time.time()
                if status.transient_error:
                    self._report(models.api_unavailable("Resolve temporarily unavailable; reconnecting"))
                    continue
                capability = (status.resolve_version, status.page if status.page and not status.page_enum else None)
                if capability != self._reported_capabilities:
                    self._reported_capabilities = capability
                    if capability[0]:
                        Log.write("Resolve version: " + str(capability[0])[:80])
                    if capability[1]:
                        Log.write("Unknown Resolve page; tracking paused: " + str(capability[1])[:80])
                self._last_status = status
                self._report(self._connection_state(status), status)

    def _read_stderr(self, proc):
        n = 0
        try:
            for raw in iter(proc.stderr.readline, b""):
                if n < 40:
                    Log.write("probe stderr: " + raw.decode("utf-8", "replace").rstrip())
                n += 1
        except Exception:
            pass

    @staticmethod
    def _connection_state(s):
        if not s.running:
            return models.RESOLVE_NOT_RUNNING
        if not s.api_ok:
            return models.api_unavailable(s.reason or "Resolve scripting isn't responding")
        return models.CONNECTED

    def _report(self, state, status=None):
        try:
            callback = self._on_update
            if callback is not None and not self._stopped.is_set():
                callback(status or self._last_status, state)
        except Exception as e:                    # never let a UI bug kill the supervisor
            Log.write("monitor callback failed: %r" % e)
