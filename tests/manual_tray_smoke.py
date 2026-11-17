"""Run the real dashboard/mini widgets under Xvfb with a fake visible tray."""
import os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['RET_DATA_DIR']=tempfile.mkdtemp()
os.environ['RET_SIGNAL_DIR']=os.environ['RET_DATA_DIR']
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker import models

app=TrackerApp(simulate=True,use_tray=False,with_resolve=True,manual=True)
d=app.popup
app.resolve_seen=True
app.icon=SimpleNamespace(visible=True)
app.state.status=models.ResolveStatus(running=True,api_ok=True,page='edit',project='Demo Project',timeline='Main Edit')
app.state.state=models.TRACKING
app.state.connection=models.CONNECTED
d.show(); app.root.update(); assert d.visible

def click_hide(window):
    def walk(w):
        for c in w.winfo_children():
            if c.winfo_class()=='TButton' and c.cget('text')=='Hide to tray':
                return c
            r=walk(c)
            if r is not None:return r
    b=walk(window); assert b is not None
    b.invoke(); app.root.update(); assert not d.visible

click_hide(d.win)
assert app.state.state==models.TRACKING
assert not app._quitting
d.show(); app.root.update(); d.compact(); app.root.update(); assert d.visible
click_hide(d.mini)
assert app.state.state==models.TRACKING
d.show(); app.root.update(); assert d.visible
app.icon=None; app.hide_window(); app.root.update()
# Xvfb without a window manager doesn't necessarily implement iconify.
d.show(); app.root.update(); assert d.visible
app.root.destroy()
print('MANUAL TRAY UI SMOKE PASSED')
