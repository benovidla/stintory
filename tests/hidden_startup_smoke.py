"""Real Tk event loop, actual subprocess monitor, simulated slow Resolve and foreground."""
import os,sys,tempfile,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve_edit_tracker import monitor,models
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker.i18n import set_language
with tempfile.TemporaryDirectory() as tmp:
    os.environ['RET_DATA_DIR']=tmp;os.environ['RET_SIGNAL_DIR']=tmp
    p=Path(tmp)/'slow.py'
    p.write_text(textwrap.dedent('''
        import time,json
        def send(**kwargs): print(json.dumps(kwargs),flush=True)
        for _ in range(3):
            send(running=True,apiOk=False,reason='loading');time.sleep(.5)
        for _ in range(4):
            send(running=True,apiOk=True,page=None);time.sleep(.5)
        while True:
            send(running=True,apiOk=True,page='edit',project='Startup project',timeline='Main');time.sleep(.5)
    '''))
    with patch.object(monitor,'PROBE_PATH',str(p)),patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=True),patch('resolve_edit_tracker.winapi.project_manager_frontmost',return_value=False):
        app=TrackerApp(with_resolve=True,use_tray=False); app.state.update_settings(trackOnlyWhenFrontmost=True,idleMinutes=5,playSoundOnStart=False); app.state.foreground_fn=lambda:(99,'resolve.exe');app.state.idle_fn=lambda:10
        app.icon=SimpleNamespace(visible=True,update_menu=Mock(),stop=Mock())
        outcome={}
        def hide():
            app.hide_window();outcome['hidden']=not app.popup.visible
        def finish():
            outcome.update(session=app.state.current,tracking=app.state.is_actively_tracking,hidden_after=not app.popup.visible);app.quit()
        app.root.after(600,hide);app.root.after(13000,finish);app.run()
        assert outcome['hidden'] and outcome['hidden_after'],outcome
        assert outcome['tracking'] and outcome['session'].project=='Startup project' and outcome['session'].duration_sec>0,outcome
print('HIDDEN STARTUP: delayed scripting, Project Manager, hide and automatic tracking passed.')
