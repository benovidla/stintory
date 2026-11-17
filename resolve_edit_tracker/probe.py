"""Resolve probe: talks to the DaVinci Resolve scripting API and prints one JSON line
roughly every 2 seconds on stdout. Runs as a separate process so a hung Resolve call can
never freeze the tracker; the tracker restarts it if it goes quiet.

    {"running": true, "apiOk": true, "page": "edit", "project": "X", "timeline": "V1",
     "timecode": "01:00:12:04", "rendering": false, "busy": false}
    {"running": true, "apiOk": true, "page": null, "project": null}          # Project Manager
    {"running": true, "apiOk": false, "reason": "scripting not responding"}  # Resolve up, API silent
    {"running": false}                                                       # Resolve not running

Standalone on purpose (no package imports). `--simulate` fakes a Resolve session so the
tracker UI can be tried without Resolve installed.
"""
import glob
import json
import os
import subprocess
import sys
import time
import threading

_DLL_HANDLES = []

POLL = 2.0
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _roots():
    seen, out = set(), []
    for var in ("PROGRAMFILES", "PROGRAMW6432", "PROGRAMFILES(X86)"):
        v = os.environ.get(var)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    for drive in "CDEFG":
        for sub in ("Program Files", "Program Files (x86)"):
            p = "%s:\\%s" % (drive, sub)
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def api_candidates():
    c = []
    env = os.environ.get("RESOLVE_SCRIPT_API")
    if env:
        c.append(env)
    if sys.platform == "darwin":
        return c + ["/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting", os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting")]
    tail = os.path.join("Blackmagic Design", "DaVinci Resolve", "Support", "Developer", "Scripting")
    for var in ("PROGRAMDATA", "APPDATA"):
        v = os.environ.get(var)
        if v:
            c.append(os.path.join(v, tail))
    c.append(os.path.join("C:\\ProgramData", tail))
    return c


def lib_candidates():
    c = []
    env = os.environ.get("RESOLVE_SCRIPT_LIB")
    if env:
        c.append(env)
    if sys.platform == "darwin":
        roots = glob.glob("/Applications/DaVinci Resolve*/*.app") + glob.glob("/Applications/DaVinci Resolve*.app")
        roots += glob.glob(os.path.expanduser("~/Applications/DaVinci Resolve*/*.app")) + glob.glob(os.path.expanduser("~/Applications/DaVinci Resolve*.app"))
        return c + [os.path.join(root, "Contents/Libraries/Fusion/fusionscript.so") for root in roots]
    for root in _roots():
        c.append(os.path.join(root, "Blackmagic Design", "DaVinci Resolve", "fusionscript.dll"))
        c.extend(glob.glob(os.path.join(root, "Blackmagic Design", "DaVinci Resolve*", "fusionscript.dll")))
    return c


def first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def emit(obj):
    try:
        os.write(1,(json.dumps(obj)+"\n").encode("utf-8"))
    except Exception:
        os._exit(0)


def norm(v):
    if v is None:
        return None
    v = str(v).strip()
    return v or None


# ------------------------------------------------------------------ process detection

_last_running = False


def resolve_running():
    """Is Resolve.exe alive? Uses tasklist (always present, needs no extra packages)."""
    global _last_running
    try:
        try:
            from resolve_edit_tracker import winapi as platform_api
        except ImportError:
            import winapi as platform_api
        running = platform_api.resolve_process_running()
        if running is not None: _last_running = running
    except Exception:
        pass
    return _last_running


def lib_from_running_process():
    """Fallback for custom install folders: ask Windows where Resolve.exe lives."""
    if sys.platform != "win32": return None
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-Process Resolve -ErrorAction SilentlyContinue | Select-Object -First 1).Path"],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
        path = out.stdout.strip()
        if path:
            cand = os.path.join(os.path.dirname(path), "fusionscript.dll")
            if os.path.exists(cand):
                return cand
    except Exception:
        pass
    return None


def setup_env():
    # Require the real vendor module, not merely an existing directory.
    api = next((p for p in api_candidates() if os.path.isfile(os.path.join(p, "Modules", "DaVinciResolveScript.py"))), None)
    override = os.environ.get("RESOLVE_SCRIPT_LIB")
    lib = first_existing([override]) or lib_from_running_process() or first_existing(lib_candidates())
    if not api:
        return None, "Resolve scripting module not found; check RESOLVE_SCRIPT_API and the local Studio installation"
    if not lib:
        return None, "DaVinci Resolve not found (fusionscript.dll). Is Resolve Studio installed?"
    if api:
        os.environ["RESOLVE_SCRIPT_API"] = api
        modules = os.path.join(api, "Modules")
        os.environ["PYTHONPATH"] = os.environ.get("PYTHONPATH", "") + os.pathsep + modules
        if modules not in sys.path:
            sys.path.insert(0, modules)
    os.environ["RESOLVE_SCRIPT_LIB"] = lib
    try:
        _DLL_HANDLES.append(os.add_dll_directory(os.path.dirname(lib)))  # keep handle alive for delayed dependencies
    except Exception:
        pass
    try:
        import DaVinciResolveScript      # noqa
        return DaVinciResolveScript, None
    except Exception as e:
        return None, "scripting module not importable (%s)" % str(e)[:120]


# ------------------------------------------------------------------ simulation

def simulate():
    """Fake Resolve for trying the UI: opens a project, cycles pages, plays back now and then."""
    start = time.time()
    pages = ["edit", "edit", "edit", "color", "edit", "fusion", "edit", "fairlight", "deliver"]
    tc = 0
    while True:
        t = time.time() - start
        if t < 4:
            emit({"running": True, "apiOk": True, "page": None, "project": None})
        else:
            i = int((t - 4) // 20) % len(pages)
            playing = int(t // 7) % 3 == 0
            if playing:
                tc += int(POLL * 24)
            fr = tc % 24
            secs = (tc // 24) % 60
            mins = (tc // 24 // 60) % 60
            emit({"running": True, "apiOk": True, "page": pages[i], "project": "Demo Project",
                  "timeline": ["Main Edit", "Social Cutdowns", "Teaser"][int((t-4)//20)%3], "timecode": "01:%02d:%02d:%02d" % (mins, secs, fr),
                  "rendering": False, "busy": False})
        time.sleep(POLL)


# ------------------------------------------------------------------ real probe

class ApiCompatibilityError(RuntimeError):
    """A required read-only capability was not available."""


def read_call(obj, method, optional=False, default=None):
    """Do not rely on version numbers or hasattr: vendor proxies may expose stubs."""
    try:
        fn = getattr(obj, method, None)
        if not callable(fn):
            raise AttributeError(method)
        return fn()
    except Exception as exc:
        if optional:
            return default
        raise ApiCompatibilityError("Resolve API call unavailable: " + method) from exc


def resolve_version(resolve):
    v = read_call(resolve, "GetVersionString", optional=True)
    if not v:
        parts = read_call(resolve, "GetVersion", optional=True)
        if isinstance(parts, (list, tuple)):
            v = ".".join(str(p) for p in parts[:4] if isinstance(p, (int, str)))
    return norm(v)


def read_text(obj, method, optional=False):
    value = read_call(obj, method, optional=optional)
    if value is None:
        return None
    if not isinstance(value, str):
        if optional:
            return None
        raise ApiCompatibilityError("Unexpected Resolve API response: " + method)
    return norm(value)


def snapshot(resolve):
    """Only read documented APIs. Missing project/timeline identity fails closed.

    Unknown pages are passed through; the consumer pauses on unrecognized pages.
    Optional playback/render data may be absent on changed API versions.
    """
    page = read_text(resolve, "GetCurrentPage")
    page = page.lower() if page else None
    pm = read_call(resolve, "GetProjectManager")
    proj = read_call(pm, "GetCurrentProject") if pm is not None else None
    name = read_text(proj, "GetName") if proj is not None else None
    tlname = tc = None
    rendering = False
    if name:
        tl = read_call(proj, "GetCurrentTimeline")
        if tl is not None:
            tlname = read_text(tl, "GetName")
            if not tlname:
                raise ApiCompatibilityError("Active timeline identity is unavailable")
            tc = read_text(tl, "GetCurrentTimecode", optional=True)
        count = read_call(proj, "GetTimelineCount", optional=True)
        # An active named timeline establishes project presence even if a later
        # API removes GetTimelineCount. Without either, do not charge stale time.
        if not tlname and not (isinstance(count, int) and not isinstance(count, bool) and count > 0):
            name = None
        if name:
            rendering = read_call(proj, "IsRenderingInProgress", optional=True) is True
    return {"running": True, "apiOk": True, "page": page, "project": name,
            "timeline": tlname if name else None, "timecode": tc if name else None,
            "rendering": rendering, "busy": page is None}


def main():
    dvr = resolve = version = None
    transient_strikes = 0
    empty_polls = 0
    while True:
        if not resolve_running():
            resolve = version = None
            transient_strikes = empty_polls = 0
            emit({"running": False})
            time.sleep(3.0)
            continue
        if dvr is None:
            dvr, reason = setup_env()
            if dvr is None:
                emit({"running": True, "apiOk": False,
                      "reason": reason or "scripting unavailable"})
                time.sleep(POLL)
                continue
        try:
            if resolve is None:
                resolve = dvr.scriptapp("Resolve")
                version = resolve_version(resolve) if resolve is not None else None
            if resolve is None:
                transient_strikes += 1
                emit({"running": True, "apiOk": False,
                      "reason": "scripting not responding (Resolve > Preferences > System > General > External scripting using: Local)"})
            else:
                data = snapshot(resolve)
                data["resolveVersion"] = version
                emit(data)
                transient_strikes = 0
                # Reacquire stale startup/manager proxies without treating a
                # legitimate Project Manager as a connection failure.
                if not data.get("page") or not data.get("project"):
                    empty_polls += 1
                    if empty_polls >= 5:
                        resolve = version = None
                        empty_polls = 0
                else:
                    empty_polls = 0
        except Exception as exc:
            transient_strikes += 1
            if transient_strikes >= 3:
                resolve = version = None
            # Do not send stale project data or private error strings.
            reason = str(exc) if isinstance(exc, ApiCompatibilityError) else "Resolve API temporarily unavailable"
            emit({"running": True, "apiOk": False, "reason": reason, "resolveVersion": version})
        # Drop the entire vendor module/connection by letting the supervisor
        # restart this process. A cached native library can outlive a bad proxy.
        if transient_strikes >= 6:
            return
        time.sleep(POLL)


def _watch_parent():
    # Kill orphaned helper even if its main thread is stuck in Resolve's API.
    if not os.environ.get("STINTORY_PARENT_PID"): return
    if sys.platform != "win32":
        parent=int(os.environ["STINTORY_PARENT_PID"])
        while os.getppid() == parent: time.sleep(2)
        os._exit(0)
    import ctypes
    from ctypes import wintypes
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; k.OpenProcess.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]; k.WaitForSingleObject.restype=wintypes.DWORD
    h=k.OpenProcess(0x00100000,False,int(os.environ['STINTORY_PARENT_PID']))
    if not h: os._exit(0)
    k.WaitForSingleObject(h,0xffffffff)
    os._exit(0)


def run(argv=None):
    threading.Thread(target=_watch_parent,daemon=True).start()
    argv = sys.argv[1:] if argv is None else argv
    try:
        if "--simulate" in argv or os.environ.get("RET_SIMULATE"):
            simulate()
        else:
            main()
    except KeyboardInterrupt:
        pass
    finally:
        os._exit(0)


if __name__ == "__main__":
    run()
