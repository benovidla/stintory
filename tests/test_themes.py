import unittest
from resolve_edit_tracker.models import Settings
from resolve_edit_tracker.themes import THEMES, OPTIONS, normalize, effective
from resolve_edit_tracker.ui_common import make_icon_image

class ThemeTests(unittest.TestCase):
    def test_roundtrip_and_legacy(self):
        for theme in THEMES:
            self.assertEqual(Settings.from_json(Settings(theme=theme).to_json()).theme, theme)
        self.assertEqual(Settings.from_json({'rate': 17}).theme, 'Steel')
        self.assertEqual(Settings.from_json({'theme': 'unknown'}).theme, 'Steel')
    def test_removed_system_palette_migrates(self):
        self.assertEqual(OPTIONS, list(THEMES))
        self.assertNotIn("System", OPTIONS)
        self.assertEqual(normalize("System"), "Steel")
        self.assertEqual(effective("System"), "Steel")
        self.assertEqual(Settings.from_json({"theme": "System"}).theme, "Steel")
    def test_brand_icon(self):
        for sz in (16,32,256):
            im=make_icon_image('brand', sz)
            self.assertEqual(im.size, (sz,sz))
            self.assertEqual(im.mode, 'RGBA')
            self.assertGreater(im.getbbox()[2], im.getbbox()[0])
