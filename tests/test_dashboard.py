import unittest
from resolve_edit_tracker.dashboard import aggregate
from resolve_edit_tracker.models import Session
class DashboardTests(unittest.TestCase):
    def test_totals(self):
        a=Session('A',0,60,60,25,'€',timeline_seconds={'Main':40,'Social':20})
        b=Session('A',60,100,40,25,'€',timeline_seconds={'Main':10})
        c=Session('B',0,20,20,25,'€',timeline_seconds={'Main':20})
        p=aggregate([a,b,c]); self.assertEqual(p['A']['total'],100); self.assertEqual(dict(p['A']['timelines']),{'Main':50,'Social':20,'Unassigned':30}); self.assertEqual(p['B']['total'],20)
    def test_overallocated(self):
        a=Session('A',0,60,60,25,'€',timeline_seconds={'Main':60,'Social':60})
        p=aggregate([a])['A']; self.assertEqual(sum(p['timelines'].values()),60)
