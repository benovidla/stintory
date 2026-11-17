import unittest, tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from resolve_edit_tracker.currencies import *
from resolve_edit_tracker.models import Settings, Session
from resolve_edit_tracker.state import AppState
from resolve_edit_tracker.store import SessionStore
from resolve_edit_tracker.invoice import invoice_rows, write_invoice
from resolve_edit_tracker.timesheet import build_html, ReportRange
from resolve_edit_tracker import fmt, csvio
from resolve_edit_tracker.dashboard import aggregate
from resolve_edit_tracker.i18n import LANGUAGES

class CurrencyTests(unittest.TestCase):
    def test_display_labels_roundtrip(self):
        self.assertEqual(set(SYMBOLS),set(CURRENCIES))
        self.assertEqual(len({currency_label(c) for c in CURRENCIES}),len(CURRENCIES))
        for code in CURRENCIES:
            self.assertEqual(currency_from_label(currency_label(code)),code)
            self.assertEqual(currency_from_label(code),code)
        for code,label in [('CZK','CZK (Kč)'),('EUR','EUR (€)'),('USD','USD ($)'),('JPY','JPY (¥)'),('CNY','CNY (¥)')]:
            self.assertEqual(currency_label(code),label)
        self.assertEqual(currency_from_label('$'),'$')
        self.assertEqual(currency_from_label('¥'),'¥')
        self.assertEqual(currency_from_label(currency_label('XAF')),'XAF')
    def test_every_language(self):
        self.assertEqual(set(LANGUAGES),set(LANGUAGE_CURRENCIES))
        for l in LANGUAGES: self.assertIn(default_currency(l,'C'), CURRENCIES)
    def test_regional_variations(self):
        for l,locale,c in [('en','en_GB','GBP'),('es','es_MX','MXN'),('pt','pt_PT','EUR'),('fr','fr_CA','CAD'),('cs','sk_SK','CZK'),('sk','en_US','EUR')]:
            self.assertEqual(default_currency(l,locale),c)
    def test_auto_new_settings(self):
        with patch('locale.getlocale',return_value=('en_US','UTF-8')):
            s=Settings.from_json(None); self.assertEqual((s.currencyMode,s.currency),('auto','USD'))
    def test_manual_migration(self):
        s=Settings.from_json({'currency':'€','rate':31,'language':'cs'}); self.assertEqual((s.currencyMode,s.currency,s.rate),('manual','€',31))
    def test_profiles_and_current(self):
        with tempfile.TemporaryDirectory() as d:
            state=AppState(store=SessionStore(d))
            state.update_settings(currencyMode='manual',currency='CZK',rate=750,projectRates={'P':900})
            state._begin_session('P'); original=state.current.to_json()
            state.update_settings(currencyMode='manual',currency='EUR')
            self.assertEqual(state.settings.rate,0);self.assertEqual(state.settings.projectRates,{})
            self.assertEqual(state.current.to_json(),original)
            state.update_settings(rate=40,projectRates={'P':50})
            state.update_settings(language='de');self.assertEqual(state.settings.currency,'EUR')
            state.update_settings(currency='CZK');self.assertEqual((state.settings.rate,state.settings.rate_for('P')),(750,900))
            state.update_settings(currency='EUR');self.assertEqual(state.settings.rate_for('P'),50)
            self.assertEqual(Settings.from_json(state.settings.to_json()).currencyProfiles,state.settings.currencyProfiles)
            state.update_settings(currencyMode='auto',language='cs');self.assertEqual(state.settings.currency,'CZK')
    def test_invoice_selection_and_override(self):
        now=datetime(2026,11,1).timestamp(); a=Session('P',now,now+3600,3600,800,'Kč');b=Session('P',now,now+3600,3600,40,'EUR'); rows=[a,b]
        self.assertEqual(invoice_rows(rows,'P','CZK')[0][2],Decimal('800.00'))
        self.assertEqual(invoice_rows(rows,'P','EUR')[0][2],Decimal('40.00'))
        self.assertEqual(invoice_rows(rows,'P','USD'),[])
        self.assertEqual(invoice_rows(rows,'P','EUR',override_rate=35)[0][2],Decimal('70.00'))
        self.assertEqual((a.rate,a.currency),(800,'Kč'))
        for bad in ('NaN','Infinity','-1'):
            with self.assertRaises(ValueError): invoice_rows(rows,'P','EUR',override_rate=bad)
    def test_grouping_and_csv(self):
        now=datetime(2026,11,1).timestamp(); rows=[Session('P',now,now+3600,3600,25,'€'),Session('P',now,now+3600,3600,30,'EUR'),Session('P',now,now+3600,3600,750,'CZK')]
        self.assertEqual(dict(aggregate(rows)['P']['earnings']),{'EUR':55,'CZK':750})
        self.assertEqual(fmt.build_stats(rows,None,'P',now).project_money,{'EUR':55,'CZK':750})
        html=build_html(rows,ReportRange(None,date(2026,11,1),date(2026,11,2)),'USD');self.assertIn('750.00 CZK',html);self.assertIn('€55.00',html);self.assertNotIn('805.00',html)
        imported=csvio.import_csv(csvio.export_csv(rows),'USD');self.assertEqual([canonical(s.currency) for s in imported],['EUR','EUR','CZK'])
    def test_minor_units_and_pdf(self):
        self.assertEqual(fmt.money(150.5,'JPY'),'151 JPY'); self.assertEqual(fmt.money(1.2345,'KWD'),'1.235 KWD')
        s=Session('P',0,1800,1800,101,'JPY');self.assertEqual(invoice_rows([s],'P','JPY')[0][2],Decimal('51'))
        with tempfile.TemporaryDirectory() as d:
            for c in ('CZK','EUR','JPY','KWD'):
                p=Path(d)/(c+'.pdf');write_invoice(p,dict(number='001',issued='2026-11-17',due='2026-12-01',supplier='Supplier',client='Client',project='P',currency=c,vat='23',language='cs'),invoice_rows([s],'P',c,override_rate=101.125));self.assertTrue(p.read_bytes().startswith(b'%PDF'))
