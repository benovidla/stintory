"""Switch all UI languages without restarting, including a live session and hidden dashboard."""
import os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve_edit_tracker import models
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker.i18n import LANGUAGES,tr

with tempfile.TemporaryDirectory() as tmp:
    os.environ['RET_DATA_DIR']=tmp;os.environ['RET_SIGNAL_DIR']=tmp
    app=TrackerApp(simulate=True,use_tray=False)
    s=app.state; d=app.popup
    s.update_settings(currencyMode='manual',currency='EUR',rate=47,invoiceLanguage='de')
    s.status=models.ResolveStatus(running=True,api_ok=True,page='edit',project='Demo Project',timeline='Main Edit')
    s.connection=models.CONNECTED;s._enter_tracking('Demo Project', 'fresh')
    session=s.current
    d.show();app.open_history();app.open_settings();app.root.update()
    for code in LANGUAGES:
        app.settings_win._language_changed('language',code);app.root.update()
        assert d.tree.heading('#0','text')==tr('PROJECT / TIMELINE',code),code
        assert app.settings_win.win.title()==tr('Stintory – Settings',code),code
        assert app.history_win.win.title()==tr('Stintory – History',code),code
        assert s.current is session and s.current.rate==47 and s.current.currency=='EUR',code
        assert s.settings.invoiceLanguage=='de' and s.state==models.TRACKING,code
    app.settings_win._language_changed('language','en');app.root.update();d.compact();app.root.update()
    app.settings_win._language_changed('language','sk');app.root.update();assert d._compact and d.mini is not None
    d.hide();app.root.update();app.settings_win._language_changed('language','en');app.root.update();assert not d.visible
    assert s.current is session
    app.quit();app.root.destroy()
print('LIVE LANGUAGE: all 20 locales, live session, compact and hidden states passed.')
