import tempfile, unittest, sys
from pathlib import Path
from decimal import Decimal
from resolve_edit_tracker.i18n import LANGUAGES,CATALOG,tr,set_language
from resolve_edit_tracker.models import Settings
from resolve_edit_tracker.invoice import write_invoice
class I18NTests(unittest.TestCase):
    def tearDown(self): set_language('en')
    def test_catalogs_equal(self):
        for lang in LANGUAGES:
            if lang != 'en': self.assertEqual(set(CATALOG[lang]),set(CATALOG['sk']))
    def test_locale_roundtrip(self):
        for lang in LANGUAGES:
            s=Settings.from_json({'language':lang,'invoiceLanguage':'es'})
            self.assertEqual(s.language,lang);self.assertEqual(s.invoiceLanguage,'es')
            self.assertEqual(Settings.from_json(s.to_json()).to_json(),s.to_json())
    def test_unknown_locale_falls_back(self):
        self.assertEqual(Settings.from_json({'language':'xxx'}).language,'en')
        self.assertEqual(tr('Custom missing key','sk'),'Custom missing key')
    def test_invoice_language_is_independent(self):
        set_language('sk');self.assertEqual(tr('INVOICE'),'FAKTÚRA');self.assertEqual(tr('INVOICE','de'),'RECHNUNG')
        with tempfile.TemporaryDirectory() as d:
            for lang in LANGUAGES:
                p=Path(d)/(lang+'.pdf')
                try:
                    write_invoice(p,dict(number='001',issued='2026-11-17',due='2026-12-01',supplier='Supplier',client='Client',project='Test <Edit>',currency='EUR',vat='23',language=lang),[(35,3600,Decimal('35.00'))])
                except RuntimeError as e:
                    if sys.platform in ('win32','darwin') and ('No local font' in str(e) or 'Raqm' in str(e)):
                        with self.subTest(language=lang): self.skipTest(str(e))
                        continue
                    raise
                self.assertTrue(p.read_bytes().startswith(b'%PDF'))
    def test_period_excludes_outside_sessions(self):
        from datetime import datetime,date
        from resolve_edit_tracker.models import Session
        from resolve_edit_tracker.invoice import invoice_rows
        a=datetime(2026,11,1,10).timestamp();b=datetime(2026,10,1,10).timestamp()
        data=[Session('P',a,a+3600,3600,50,'EUR'),Session('P',b,b+3600,3600,50,'EUR')]
        self.assertEqual(invoice_rows(data,'P','EUR',date(2026,11,1),date(2026,11,30))[0][2],Decimal('50.00'))
