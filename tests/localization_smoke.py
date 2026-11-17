"""Xvfb GUI test: launch every language against isolated demo data."""
import os,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve_edit_tracker.i18n import LANGUAGES,tr
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker.invoice import InvoiceWindow
from resolve_edit_tracker.models import Settings
from PIL import ImageGrab
for lang in LANGUAGES:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['RET_DATA_DIR']=tmp;os.environ['RET_SIGNAL_DIR']=tmp
        Path(tmp,'settings.json').write_text(json.dumps(Settings(language=lang,invoiceLanguage=lang).to_json()))
        app=TrackerApp(simulate=True,use_tray=False)
        app.popup.show();app.root.update()
        assert app.popup.tree.heading('#0','text')==tr('PROJECT / TIMELINE',lang)
        app.open_settings();app.root.update();assert app.settings_win.win.title()==tr('Stintory – Settings',lang);app.settings_win._close()
        app.open_history();app.root.update();assert app.history_win.win.title()==tr('Stintory – History',lang);app.history_win._close()
        inv=InvoiceWindow(app.popup.win,app.state,'Demo Project');app.root.update();assert inv.lang.get()==LANGUAGES[lang];inv.win.destroy()
        app.popup.win.geometry('1200x790+20+20');app.root.update()
        if len(sys.argv)>1:
            p=Path(sys.argv[1]);p.mkdir(exist_ok=True,parents=True);w=app.popup.win;x,y=w.winfo_rootx(),w.winfo_rooty();ImageGrab.grab(xdisplay=os.environ['DISPLAY'],bbox=(x,y,x+w.winfo_width(),y+w.winfo_height())).save(p/(lang+'.png'))
        app.quit();app.root.destroy()
print(f'All {len(LANGUAGES)} UI locales opened dashboard, settings, history and invoice.')
