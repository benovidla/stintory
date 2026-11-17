"""Exercise the real settings and invoice controls in a Linux Xvfb session."""
import sys, os, tempfile
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker.models import Session
from resolve_edit_tracker.invoice import InvoiceWindow
from resolve_edit_tracker.currencies import canonical, currency_label
from datetime import datetime

with tempfile.TemporaryDirectory() as tmp:
    os.environ['RET_DATA_DIR']=tmp; os.environ['RET_SIGNAL_DIR']=tmp
    app=TrackerApp(simulate=True,use_tray=False)
    app.popup.show(); app.root.update()
    state=app.state
    state.update_settings(currencyMode='manual',currency='CZK',rate=800)
    now=datetime.now().timestamp()
    state.store.replace_all([Session('Currency demo',now,now+3600,3600,800,'CZK'),Session('Currency demo',now,now+3600,3600,40,'EUR')])
    app.open_settings();app.root.update();w=app.settings_win
    assert w.cur_var.get()=='CZK (Kč)'
    w.cur_var.set(currency_label('EUR'));w._currency_changed();app.root.update()
    assert state.settings.currency=='EUR' and state.settings.rate==0
    w.rate_var.set('35');assert state.settings.rate==35
    w.cur_var.set(currency_label('CZK'));w._currency_changed();assert state.settings.rate==800
    w.cur_combo.current(0);w._currency_changed();w._language_changed('language','cs')
    assert state.settings.currency=='CZK' and state.settings.currencyMode=='auto'
    w._language_changed('language','ja');assert state.settings.currency=='JPY'
    w.cur_var.set(currency_label('EUR'));w._currency_changed();assert state.settings.rate==35
    w._language_changed('language','cs');assert state.settings.currency=='EUR'
    w._close();app.root.update()
    inv=InvoiceWindow(app.popup.win,state,'Currency demo');app.root.update()
    assert inv.currency.get()=='EUR (€)' and inv._rows(None,None)[0][2]==Decimal('40.00')
    inv.override.set('35');assert inv._rows(None,None)[0][2]==Decimal('70.00')
    inv.currency.set(currency_label('CZK'));inv.change_currency();assert inv.override.get()=='' and inv._rows(None,None)[0][2]==Decimal('800.00')
    inv.currency.set(currency_label('EUR'));inv.change_currency();inv.override.set('35');assert inv._rows(None,None)[0][2]==Decimal('70.00')
    assert len(inv.currencies['values'])>=53
    assert 'USD ($)' in inv.currencies['values'] and 'JPY (¥)' in inv.currencies['values']
    assert state.settings.currency=='EUR'
    inv.win.destroy();app.quit();app.root.destroy()
print('Currency settings and invoice UI smoke passed.')
