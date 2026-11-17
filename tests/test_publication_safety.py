import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from scripts.package_sources import allowed
from resolve_edit_tracker.invoice_fonts import allows_pdf_subset

class PublicationSafety(unittest.TestCase):
    def test_source_allowlist(self):
        for f in ['sessions.json','invoice.pdf','private.csv','setup-linked.log','launcher-config.txt','resolve_edit_tracker/assets/font.ttf','resolve_edit_tracker/assets/fusionscript.dll','resolve_edit_tracker/DaVinciResolveScript.py','docs/examples/client.pdf','personal-token.txt']:
            self.assertFalse(allowed(Path(f)),f)
        for f in ['LICENSE','THIRD_PARTY_NOTICES.md','README.md','resolve_edit_tracker/probe.py','resolve_edit_tracker/assets/icon.png','scripts/package_sources.py','tests/test_state.py','.github/workflows/ci.yml','docs/COMPATIBILITY.md']:
            self.assertTrue(allowed(Path(f)),f)
    def test_font_embedding_flags(self):
        for flag,expected in [(0,True),(4,True),(8,True),(2,False),(0x100,False),(0x200,False),(0x104,False)]:
            with self.subTest(flag=flag),patch('fontTools.ttLib.TTFont') as font:
                font.return_value.__enter__.return_value.__getitem__.return_value.fsType=flag
                allows_pdf_subset.cache_clear()
                self.assertEqual(allows_pdf_subset('dummy.ttf'),expected)
        allows_pdf_subset.cache_clear()
    def test_bad_font_denied(self):
        with patch('fontTools.ttLib.TTFont',side_effect=OSError):
            allows_pdf_subset.cache_clear();self.assertFalse(allows_pdf_subset('dummy.ttf'))
        allows_pdf_subset.cache_clear()

if __name__=='__main__':unittest.main()
