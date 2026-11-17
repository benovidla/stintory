"""Small shared helpers: data folder, logging, ISO dates, atomic JSON writes."""
import json
import os
import re
import threading
import time
import sys
import tempfile
from datetime import datetime, timezone


def data_dir():
    override = os.environ.get("RET_DATA_DIR")
    if override:
        base = override
    else:
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support/Stintory")
        else:
            root = os.environ.get("APPDATA") or os.path.expanduser("~")
            base = os.path.join(root, "ResolveEditTracker")
    os.makedirs(base, exist_ok=True)
    return base


def signal_dir():
    """Where one launch drops small flag files for the already-running one."""
    override = os.environ.get("RET_SIGNAL_DIR")
    root = override or data_dir()
    os.makedirs(root, exist_ok=True)
    return root


def to_iso(ts):
    """Epoch seconds -> 2026-08-31T19:20:00Z (same shape the macOS app writes)."""
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_FRAC = re.compile(r"\.\d+")


def from_iso(s):
    if not isinstance(s, str):
        raise ValueError("not a date string")
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    t = _FRAC.sub("", t, count=1)
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        return dt.timestamp()
    return dt.timestamp()


def write_json_atomic(path, obj):
    path = os.fspath(path)
    fd, tmp = tempfile.mkstemp(prefix=".stintory-", suffix=".tmp", dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Log:
    """Append-only debug.log in the data folder; trims itself when it grows past 1 MB."""
    _lock = threading.Lock()
    _path = None
    MAX_BYTES = 1_000_000
    KEEP_BYTES = 200_000

    @classmethod
    def path(cls):
        if cls._path is None:
            cls._path = os.path.join(data_dir(), "debug.log")
        return cls._path

    @classmethod
    def write(cls, message):
        line = "[%s] %s\n" % (datetime.now().strftime("%H:%M:%S.%f")[:-3], message)
        with cls._lock:
            try:
                p = cls.path()
                if os.path.exists(p) and os.path.getsize(p) > cls.MAX_BYTES:
                    with open(p, "rb") as f:
                        f.seek(-cls.KEEP_BYTES, os.SEEK_END)
                        tail = f.read()
                    with open(p, "wb") as f:
                        f.write(tail)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                pass
        if os.environ.get("RET_DEBUG"):
            print(line, end="")
