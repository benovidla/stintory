import tempfile, unittest
from pathlib import Path
from decimal import Decimal
from resolve_edit_tracker.invoice import invoice_rows, write_invoice
from resolve_edit_tracker.models import Session
from resolve_edit_tracker.store import SessionStore
class InvoiceTests(unittest.TestCase):
    def test_mixed_currency_rates(self):
        rows=invoice_rows([Session('A',0,3600,3600,25,'EUR'),Session('A',0,1800,1800,40,'EUR'),Session('A',0,3600,3600,99,'USD')],'A','EUR')
        self.assertEqual([r[2] for r in rows],[Decimal('25.00'),Decimal('20.00')])
    def test_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'invoice.pdf';write_invoice(p,dict(number='001',issued='2026-11-17',due='2026-12-01',supplier='Test s.r.o.',client='Client & Co',project='Test <Edit>',currency='EUR',vat='23'),[(35,3600,Decimal('35.00'))]);self.assertTrue(p.read_bytes().startswith(b'%PDF'))
    def test_checkpoint_updates_mutated_dict(self):
        with tempfile.TemporaryDirectory() as d:
            store=SessionStore(d);s=Session('A',0,1,1,25,'EUR',page_seconds={'edit':1});store.save_current(s);s.page_seconds['edit']=3;s.duration_sec=3;store.save_current(s);self.assertEqual(store.load_current().page_seconds['edit'],3)
