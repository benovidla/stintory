"""Thin Windows helpers (ctypes only, no third-party packages).

Every function degrades to a harmless default on other platforms so the rest of the
app (and the test-suite) can run anywhere.
"""
import os
import subprocess
import sys

IS_WIN = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0

if IS_WIN:
    import ctypes
    from ctypes import wintypes
    import winreg
    import winsound

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    kernel32.GetTickCount.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long


APP_USER_MODEL_ID = "Stintory.Desktop"


def set_app_identity():
    """Assign a stable taskbar identity before any Tk window is created."""
    if not IS_WIN:
        return False
    try:
        fn = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes = [wintypes.LPCWSTR]
        fn.restype = ctypes.c_long
        return fn(APP_USER_MODEL_ID) == 0
    except (AttributeError, OSError):
        return False


def set_dpi_aware():
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def idle_seconds():
    """Seconds since the last keyboard/mouse input (GetLastInputInfo, no hooks, no permissions)."""
    if not IS_WIN:
        return 0.0
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        now = kernel32.GetTickCount()
        return ((now - lii.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:
        return 0.0


def foreground_info():
    """(pid, exe_basename_lowercase_or_None) of the foreground window, or None if unknown."""
    if not IS_WIN:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        h = kernel32.OpenProcess(0x1000, False, pid.value)    # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return (pid.value, None)
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        finally:
            kernel32.CloseHandle(h)
        return (pid.value, os.path.basename(buf.value).lower() if ok else None)
    except Exception:
        return None



def is_project_manager_title(title, owned=False):
    """Conservative: explicit manager name or a Resolve-branded owned dialog.

    Never infer it from a project name or an arbitrary popup.
    """
    import re
    text=' '.join((title or '').split()).casefold()
    if text in ('project manager', 'davinci resolve project manager'):
        return True
    return bool(owned and re.fullmatch(r'davinci resolve(?: studio)?(?: \d+(?:\.\d+)*)?', text))


def project_manager_frontmost():
    """Best-effort Windows fallback when scripting still reports the old page."""
    if not IS_WIN:
        return False
    try:
        hwnd=user32.GetForegroundWindow()
        if not hwnd: return False
        info=foreground_info()
        if not info or info[1] != 'resolve.exe': return False
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value != info[0] or hwnd != user32.GetForegroundWindow(): return False
        get_text=user32.GetWindowTextW
        get_text.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        get_text.restype=ctypes.c_int
        title=ctypes.create_unicode_buffer(512)
        get_text(hwnd,title,512)
        get_window=user32.GetWindow
        get_window.argtypes=[wintypes.HWND,wintypes.UINT]
        get_window.restype=wintypes.HWND
        owner=get_window(hwnd,4)  # GW_OWNER
        owner_pid=wintypes.DWORD()
        if owner: user32.GetWindowThreadProcessId(owner,ctypes.byref(owner_pid))
        return is_project_manager_title(title.value, bool(owner and owner_pid.value==pid.value))
    except (AttributeError,OSError,ValueError):
        return False

_mutex_handle = None


def acquire_single_instance(name="Local\\ResolveEditTrackerSingleton"):
    """True if we are the only instance."""
    global _mutex_handle
    if not IS_WIN:
        return True
    _mutex_handle = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183          # ERROR_ALREADY_EXISTS


# ---------------------------------------------------------------- launch at login

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "ResolveEditTracker"


def autostart_enabled():
    if not IS_WIN:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, _RUN_NAME)
            return True
    except OSError:
        return False


def autostart_set(enabled, command):
    """Returns the effective state after the attempt."""
    if not IS_WIN:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, _RUN_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(k, _RUN_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass
    return autostart_enabled()


# ---------------------------------------------------------------- sounds

_MEDIA = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Media")
PREFERRED_SOUNDS = [
    "Windows Notify System Generic", "Windows Notify Messaging", "Windows Ding",
    "Windows Notify Calendar", "Windows Notify Email", "chimes", "notify", "tada", "ding",
]


def list_sounds():
    try:
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(_MEDIA) if f.lower().endswith(".wav"))
    except OSError:
        names = []
    first = [n for n in PREFERRED_SOUNDS if n in names]
    rest = [n for n in names if n not in first]
    return first + rest


def play_sound(name):
    if not IS_WIN:
        return
    try:
        path = os.path.join(_MEDIA, name + ".wav")
        if os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


# ---------------------------------------------------------------- windows & screen

class _RECT(ctypes.Structure if IS_WIN else object):
    if IS_WIN:
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _POINT(ctypes.Structure if IS_WIN else object):
    if IS_WIN:
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def work_area():
    """(left, top, right, bottom) of the primary monitor minus the taskbar."""
    if IS_WIN:
        try:
            r = _RECT()
            if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):     # SPI_GETWORKAREA
                return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
    return None


def cursor_pos():
    if IS_WIN:
        try:
            p = _POINT()
            if user32.GetCursorPos(ctypes.byref(p)):
                return (p.x, p.y)
        except Exception:
            pass
    return None


def make_toast_window(toplevel):
    """Click-through, non-activating, hidden from Alt-Tab: a toast must never steal focus from Resolve."""
    if not IS_WIN:
        return
    try:
        hwnd = user32.GetParent(toplevel.winfo_id()) or toplevel.winfo_id()
        GWL_EXSTYLE = -20
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= 0x00000020 | 0x08000000 | 0x00000080 | 0x00080000   # TRANSPARENT|NOACTIVATE|TOOLWINDOW|LAYERED
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass


def force_foreground(toplevel):
    """Windows' foreground lock can refuse focus to a window opened from a tray click.
    A synthetic Alt tap is the usual way to lift that restriction for one SetForegroundWindow call."""
    if not IS_WIN:
        return
    try:
        hwnd = user32.GetParent(toplevel.winfo_id()) or toplevel.winfo_id()
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def hide_from_taskbar(toplevel):
    if not IS_WIN:
        return
    try:
        hwnd = user32.GetParent(toplevel.winfo_id()) or toplevel.winfo_id()
        GWL_EXSTYLE = -20
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style | 0x00000080) & ~0x00040000                       # TOOLWINDOW, not APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass


def system_is_dark():
    if not IS_WIN:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def open_path(path):
    try:
        if IS_WIN:
            os.startfile(path)                                           # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def resolve_process_running():
    """Independent OS process check, even when Resolve scripting is hung.
    None means unavailable; do not treat an OS query failure as a process exit.
    """
    if not IS_WIN:
        return None
    try:
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',ctypes.c_long),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
        snap=kernel32.CreateToolhelp32Snapshot; snap.argtypes=[wintypes.DWORD,wintypes.DWORD]; snap.restype=wintypes.HANDLE
        first=kernel32.Process32FirstW; nxt=kernel32.Process32NextW
        for fn in (first,nxt):
            fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32W)]; fn.restype=wintypes.BOOL
        session=kernel32.ProcessIdToSessionId; session.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]; session.restype=wintypes.BOOL
        own=wintypes.DWORD(); other=wintypes.DWORD()
        if not session(os.getpid(),ctypes.byref(own)): return None
        h=snap(2,0)
        if h in (None,ctypes.c_void_p(-1).value): return None
        try:
            p=PROCESSENTRY32W(); p.dwSize=ctypes.sizeof(p)
            if not first(h,ctypes.byref(p)): return None
            while True:
                if p.szExeFile.lower()=='resolve.exe' and session(p.th32ProcessID,ctypes.byref(other)) and other.value==own.value: return True
                if not nxt(h,ctypes.byref(p)): break
            return False
        finally: kernel32.CloseHandle(h)
    except Exception: return None

# macOS platform adapter. Kept here to preserve the existing injectable API.
if sys.platform == 'darwin':
    def _workspace():
        from AppKit import NSWorkspace
        return NSWorkspace.sharedWorkspace()

    def _is_resolve(app):
        if app is None: return False
        bundle = str(app.bundleIdentifier() or '').lower()
        name = str(app.localizedName() or '').lower()
        return bundle in ('com.blackmagic-design.davinciresolve', 'com.blackmagic-design.davinciresolve.studio') or name == 'davinci resolve'

    def resolve_process_running():
        try: return any(_is_resolve(a) for a in _workspace().runningApplications())
        except Exception: return None

    def foreground_info():
        try:
            app = _workspace().frontmostApplication()
            return int(app.processIdentifier()), 'resolve' if _is_resolve(app) else str(app.localizedName() or '').lower()
        except Exception: return None

    def idle_seconds():
        try:
            import Quartz as q
            return float(q.CGEventSourceSecondsSinceLastEventType(q.kCGEventSourceStateCombinedSessionState, q.kCGAnyInputEventType))
        except Exception: return 0.0

    _lock_file = None
    def acquire_single_instance(name='Local\\ResolveEditTrackerSingleton'):
        import fcntl
        global _lock_file
        # Environment-independent production and separately isolated demo locks.
        root = os.path.expanduser('~/Library/Application Support/Stintory')
        if 'Demo' in name: root = os.environ.get('RET_DATA_DIR',root)
        os.makedirs(root, exist_ok=True)
        f = open(os.path.join(root,'instance.lock'),'a+')
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: f.close(); return False
        _lock_file=f
        return True

    def system_is_dark():
        try:
            from Foundation import NSUserDefaults
            return str(NSUserDefaults.standardUserDefaults().stringForKey_('AppleInterfaceStyle') or '').lower() == 'dark'
        except Exception: return False

    def list_sounds():
        try: return sorted(os.path.splitext(x)[0] for x in os.listdir('/System/Library/Sounds') if x.endswith('.aiff'))
        except OSError: return []

    def play_sound(name):
        path = os.path.join('/System/Library/Sounds', os.path.basename(name)+'.aiff')
        if not os.path.isfile(path): path='/System/Library/Sounds/Glass.aiff'
        try: subprocess.Popen(['/usr/bin/afplay',path],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except OSError: pass

    def autostart_enabled():
        return os.path.isfile(os.path.expanduser('~/Library/LaunchAgents/org.stintory.tracker.plist'))
