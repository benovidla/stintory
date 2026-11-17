"""Adverse inputs, simulated disk failures, repeatable state sequences, locale coverage."""
import json, math, random, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal
from resolve_edit_tracker import csvio, models
from resolve_edit_tracker.i18n import LANGUAGES,CATALOG,tr,code_for
from resolve_edit_tracker.invoice import write_invoice,invoice_rows
from resolve_edit_tracker.store import SessionStore
from resolve_edit_tracker.dashboard import aggregate
from resolve_edit_tracker.state import AppState
from resolve_edit_tracker.util import write_json_atomic

class ReleaseSafetyTests(unittest.TestCase):
    def test_all_locale_keys_and_placeholders(self):
        import re
        expected=set(CATALOG['sk'])
        self.assertEqual(len(LANGUAGES),20)
        self.assertEqual(list(LANGUAGES)[:10],['en','zh','hi','es','ar','fr','bn','pt','id','ur'])
        for code,name in LANGUAGES.items():
            self.assertEqual(code_for(name),code)
            if code=='en': continue
            self.assertEqual(set(CATALOG[code]),expected)
            for key,val in CATALOG[code].items():
                self.assertTrue(val.strip(),(code,key))
                self.assertEqual(re.findall(r'%[ds]',key),re.findall(r'%[ds]',val),(code,key))
    def test_reject_nonfinite_session(self):
        with tempfile.TemporaryDirectory() as d:
            s=SessionStore(d)
            for bad in (float('nan'),float('inf'),-1):
                with self.assertRaises(ValueError): s.append(models.Session('P',0,1,bad,25,'EUR'))
            self.assertEqual(s.sessions,[])
    def test_invalid_settings(self):
        s=models.Settings.from_json({'rate':'nan','projectRates':{'A':'Infinity','B':-2,'C':12},'idleMinutes':999})
        self.assertEqual(s.rate,25);self.assertEqual(s.projectRates,{'C':12});self.assertEqual(s.idleMinutes,240)
    def test_history_corruption_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sessions.json';p.write_bytes(b'{bad')
            with self.assertRaises(RuntimeError):SessionStore(d)
            self.assertEqual(p.read_bytes(),b'{bad')
    def test_invalid_history_row_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sessions.json';p.write_text('[null]')
            with self.assertRaises(RuntimeError):SessionStore(d)
            self.assertEqual(p.read_text(),'[null]')
    def test_disk_error_does_not_commit(self):
        with tempfile.TemporaryDirectory() as d:
            s=SessionStore(d); a=models.Session('A',0,10,10,5,'EUR');s.append(a);v=s.version
            with patch('resolve_edit_tracker.store.write_json_atomic',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):s.append(models.Session('B',0,10,10,2,'EUR'))
                with self.assertRaises(OSError):s.delete([a.id])
            self.assertEqual(s.version,v);self.assertEqual(len(s.sessions),1);self.assertEqual(len(SessionStore(d).sessions),1)
    def test_atomic_write_failure_preserves_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.json';write_json_atomic(p,{'old':1})
            with patch('resolve_edit_tracker.util.os.replace',side_effect=OSError('failed')):
                with self.assertRaises(OSError):write_json_atomic(p,{'new':2})
            self.assertEqual(json.loads(p.read_text()),{'old':1});self.assertEqual(list(Path(d).glob('*.tmp')),[])
    def test_recovery_idempotent_and_legacy_duration(self):
        with tempfile.TemporaryDirectory() as d:
            st=SessionStore(d); a=models.Session('A',1,31,30,25,'EUR');st.save_current(a)
            kw=dict(clock=lambda:100.,idle_fn=lambda:0,foreground_fn=lambda:(12,'resolve.exe'),autostart_get=lambda:False,autostart_set=lambda *a:False)
            app=AppState(store=SessionStore(d),**kw);self.assertEqual(app.sessions[0].duration_sec,30)
            app.store.save_current(a);app=AppState(store=SessionStore(d),**kw);self.assertEqual(len(app.sessions),1)
    def test_corrupt_checkpoint_is_quarantined(self):
        with tempfile.TemporaryDirectory() as d:
            s=SessionStore(d);Path(s.current_path).write_text('bad')
            self.assertIsNone(s.load_current());self.assertEqual(len(list(Path(d).glob('current.json.corrupt-*'))),1)
    def test_repeated_append_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            s=SessionStore(d);a=models.Session('A',0,10,10,5,'EUR');s.append(a);s.append(a);self.assertEqual(len(s.sessions),1)
    def test_csv_rejects_invalid_durations_and_escapes_formulas(self):
        self.assertEqual(csvio.import_csv('2026-01-01 12:00,NaN,10\n2026-01-01 12:00,-5,10','EUR'),[])
        s=models.Session('A',0,10,10,5,'EUR',note=' =1+1');self.assertIn("' =1+1",csvio.export_csv([s]))
    def test_randomized_rollups(self):
        rng=random.Random(42)
        for _ in range(100):
            sessions=[models.Session(rng.choice(['A','B','C']),0,10,rng.randrange(1,500),25,'EUR',timeline_seconds={'one':rng.randrange(500),'two':rng.randrange(500)}) for i in range(30)]
            projects=aggregate(sessions)
            self.assertAlmostEqual(sum(p['total'] for p in projects.values()),sum(s.duration_sec for s in sessions),places=5)
            for p in projects.values():self.assertAlmostEqual(sum(p['timelines'].values()),p['total'],places=5)
    def test_failed_pdf_does_not_replace_existing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.pdf';p.write_bytes(b'existing')
            f=dict(number='1',issued='2026-01-01',due='2026-01-02',supplier='Supplier',client='Client',project='P',currency='EUR',vat='0',language='en')
            with patch('resolve_edit_tracker.invoice_fonts.supports_text',return_value=False),patch('resolve_edit_tracker.invoice_fonts.raster_paragraph',side_effect=RuntimeError('no font')):
                with self.assertRaises(RuntimeError):write_invoice(p,f,[(25,3600,Decimal('25'))])
            self.assertEqual(p.read_bytes(),b'existing')

if __name__=='__main__':unittest.main()
