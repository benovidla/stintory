"""Launch the real Resolve and Stintory, retaining Unicode paths and logging failures."""
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent


def launch(root, popen=subprocess.Popen):
    resolve, pythonw, args, work = (root/'launcher-config.txt').read_text(encoding='utf-16').splitlines()[:4]
    if not Path(resolve).is_file() or not Path(pythonw).is_file():
        raise FileNotFoundError('Resolve or Python has moved. Run REPAIR-LINKED.bat again.')
    env=dict(os.environ); env.pop('PYTHONHOME',None); env.pop('PYTHONPATH',None)
    # Preserve the original shortcut's Windows command line arguments.
    popen(subprocess.list2cmdline([resolve])+' '+args,cwd=work,env=env)
    return popen([pythonw,'-E',str(root/'run_tracker.pyw'),'--with-resolve','--wait-resolve','--linked-launch'],cwd=root,env=env)


if __name__=='__main__':
    try:
        from resolve_edit_tracker.util import Log
        Log.write('Linked shortcut invoked')
        launch(ROOT)
        Log.write('Linked shortcut started Resolve and tracker')
    except Exception:
        from resolve_edit_tracker.util import Log
        Log.write('Linked launcher error: '+traceback.format_exc())
        import ctypes
        ctypes.windll.user32.MessageBoxW(0,'Stintory launcher failed. See debug.log in the data folder.','Stintory',0x10)
        sys.exit(1)
