"""Headless theme switch smoke test; run with xvfb-run on Linux."""
import os, sys, tempfile, json
from pathlib import Path
os.environ['RET_DATA_DIR']=tempfile.mkdtemp()
os.environ['RET_SIGNAL_DIR']=os.environ['RET_DATA_DIR']
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import ImageGrab
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker.themes import THEMES
from resolve_edit_tracker import models
app=TrackerApp(simulate=True,use_tray=False)
d=app.popup
app.state.status=models.ResolveStatus(running=True,api_ok=True,page='edit',project='Demo Project',timeline='Main Edit')
app.state.active_project='Demo Project'
app.state.connection=models.CONNECTED
app.state.state=models.TRACKING
d.show(); app.root.update(); d.win.geometry('1200x790+30+30'); app.root.update()
# exercise the actual settings callback
app.open_settings(); app.root.update()
assert tuple(app.settings_win.theme_combo.cget("values"))==tuple(THEMES)
for name,p in THEMES.items():
    app.settings_win.theme_var.set(name)
    app.settings_win._theme_changed()
    assert app.state.settings.theme==name
    assert d.win.cget('bg')==p['BG'], (name,d.win.cget('bg'))
    assert d.timer.cget('fg')==p['GREEN']
    assert str(d.tree.tag_configure('live','foreground'))==p['GREEN']
    if Path(app.state.settings_path).exists(): assert json.loads(Path(app.state.settings_path).read_text())['theme']==name
    d.compact(); app.root.update(); assert d.mini.cget('bg')==p['PANEL']; assert d.mini_time.cget('fg')==p['GREEN']; d.show()
    app.settings_win.win.withdraw(); app.root.update(); d.win.lift(); app.root.update()
    if len(sys.argv)>1:
        path=Path(sys.argv[1]); path.mkdir(exist_ok=True)
        x,y=d.win.winfo_rootx(),d.win.winfo_rooty(); w,h=d.win.winfo_width(),d.win.winfo_height()
        ImageGrab.grab(xdisplay=os.environ['DISPLAY'],bbox=(x,y,x+w,y+h)).save(path/(name+'.png'))
# Ensure an already-created mini window recolors across all themes
for name,p in THEMES.items():
    d.apply_theme(name); assert d.mini.cget('bg')==p['PANEL']
app.root.destroy(); print('THEME UI SMOKE PASSED')
