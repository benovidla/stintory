import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image
from resolve_edit_tracker.ui_common import make_icon_image
from resolve_edit_tracker.themes import THEMES
from resolve_edit_tracker.models import Settings
from scripts.package_sources import allowed
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'resolve_edit_tracker/assets'
class BrandAssetsTests(unittest.TestCase):
    def test_vectors_are_self_contained(self):
        for name in ('logo.svg','logo-light.svg','symbol.svg','app.svg','tray.svg','wordmark.svg'):
            p=A/name; text=p.read_text(); root=ET.fromstring(text)
            self.assertTrue(root.tag.endswith('svg'));self.assertNotIn('<text',text);self.assertNotIn('<image',text)
            self.assertTrue(allowed(p.relative_to(ROOT)))
    def test_rasters_and_ico(self):
        for name,size in [('brand.png',(2760,840)),('brand_light.png',(2760,840)),('icon.png',(1024,1024)),('tray.png',(256,256))]:
            with Image.open(A/name) as im:
                self.assertEqual(im.size,size);self.assertEqual(im.mode,'RGBA')
        self.assertEqual((ROOT/'app.ico').read_bytes(),(A/'app.ico').read_bytes())
        with Image.open(A/'app.ico') as im:
            self.assertEqual(im.ico.sizes(),{(x,x) for x in (16,24,32,48,64,128,256)})
        for size in (16,24,32,64,256):
            self.assertEqual(make_icon_image('tracking',size).size,(size,size))
    def test_new_default_preserves_previous_palettes(self):
        self.assertEqual(Settings().theme,'Steel'); self.assertEqual(len(THEMES),9)
        for name in THEMES:
            self.assertEqual(Settings.from_json({'theme':name}).theme,name)
if __name__=='__main__':unittest.main()
