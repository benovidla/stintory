import os
import sys
import traceback

from . import winapi
from .util import Log, data_dir, signal_dir


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--version" in argv:
        from . import __version__
        print("Stintory " + __version__)
        return

    if "--probe" in argv:                                   # frozen build: re-enter as the Resolve helper
        from . import probe
        probe.run([a for a in argv if a != "--probe"])
        return

    if "--toggle-pause" in argv:                            # for hotkey tools / Stream Deck
        open(os.path.join(data_dir(), "toggle.pause"), "w").close()
        return

    if "--open" in argv:                                    # open the panel of the running tracker
        open(os.path.join(signal_dir(), "open.panel"), "w").close()
        return

    if "--enable-resident" in argv:
        if sys.platform != "win32": raise SystemExit("Use the macOS installer")
        import subprocess
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "run_tracker.pyw"))
        if not os.path.isfile(pythonw): raise SystemExit("pythonw.exe not found")
        root=os.path.dirname(script)
        from pathlib import Path
        Path(root,'resident-python.txt').write_text(pythonw+'\n',encoding='utf-16')
        command = subprocess.list2cmdline([os.path.join(os.environ['WINDIR'],'System32','wscript.exe'), os.path.join(root,'launch_resident.vbs')])
        if not winapi.autostart_set(True, command): raise SystemExit("Could not enable login startup")
        return
    if "--disable-autostart" in argv:
        if winapi.autostart_set(False, ""):
            raise SystemExit("Could not remove legacy startup entry")
        return

    if "--scheduled" in argv and winapi.resolve_process_running() is not True:
        return

    if "--resident" in argv and "--with-resolve" in argv:
        raise SystemExit("Choose one launch mode")
    # Explicit user launch is a review window when Resolve is absent, not a
    # second offline process which could block the real tracker from starting.
    if "--manual" in argv and not any(x in argv for x in ("--resident", "--with-resolve", "--offline")):
        from pathlib import Path
        try:
            mode = (Path(__file__).resolve().parents[1] / "launch-mode.txt").read_text(encoding="utf-8").strip()
        except OSError:
            mode = "linked"
        argv.append("--resident" if mode == "resident" else "--with-resolve")
    # Resident mode remains open; linked mode stops with Resolve.
    if not any(x in argv for x in ("--simulate", "--offline", "--resident")):
        if "--with-resolve" not in argv: argv.append("--with-resolve")
        if winapi.resolve_process_running() is False and not any(x in argv for x in ("--wait-resolve", "--manual")):
            return

    if "--simulate" in argv:
        import tempfile
        os.environ["RET_DATA_DIR"] = tempfile.mkdtemp(prefix="StintoryDemo-")
        os.environ["RET_SIGNAL_DIR"] = os.environ["RET_DATA_DIR"]
    if not winapi.acquire_single_instance("Local\\ResolveEditTrackerDemo" if "--simulate" in argv else "Local\\ResolveEditTrackerSingleton"):
        # Already running: starting it again simply brings up its panel
        # (unless the Resolve launcher started us, then stay quiet).
        if not any(flag in argv for flag in ("--background", "--scheduled", "--linked-launch")):
            open(os.path.join(signal_dir(), "open.panel"), "w").close()
        return

    try:
        Log.write("Tracker started: " + " ".join(argv))
        from .app import TrackerApp
        TrackerApp(simulate="--simulate" in argv, use_tray="--no-tray" not in argv,
                   with_resolve="--with-resolve" in argv, background="--background" in argv, offline="--offline" in argv, manual="--manual" in argv).run()
    except Exception:
        Log.write("fatal: " + traceback.format_exc().strip())
        try:
            from tkinter import messagebox
            if "--scheduled" not in argv: messagebox.showerror("Stintory", "The tracker crashed. Details are in\n%s" % Log.path())
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
