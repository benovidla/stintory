import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _report_crash(tb):
    """Never die silently: write crash.log, print it, and show a message box on Windows."""
    try:
        from resolve_edit_tracker.util import data_dir
        root = data_dir()
        os.makedirs(root, exist_ok=True)
        with open(os.path.join(root, "crash.log"), "a", encoding="utf-8") as f:
            f.write(tb + "\n")
    except Exception:
        pass
    try:
        print(tb)
    except Exception:
        pass
    if "--scheduled" in sys.argv: return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, tb[-1200:], "Stintory crashed", 0x10)
    except Exception:
        pass



if __name__ == "__main__":
    try:
        from resolve_edit_tracker.__main__ import main
        # Installed default applies only to ordinary (no-argument) launches.
        args=sys.argv[1:]
        if not args:
            try:
                mode=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'launch-mode.txt'), encoding='utf-8').read().strip()
            except OSError: mode='linked'
            args=['--resident'] if mode=='resident' else ['--manual','--with-resolve']
        main(args)
    except SystemExit:
        raise
    except BaseException:
        _report_crash(traceback.format_exc())
        sys.exit(1)
