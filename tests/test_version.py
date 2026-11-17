import unittest
import re
import subprocess
import sys
from pathlib import Path
from resolve_edit_tracker import __version__
from scripts.package_sources import VERSION,entries,ROOT

class ReleaseVersionTests(unittest.TestCase):
    def test_version_consistent(self):
        self.assertEqual(VERSION,__version__)
        self.assertRegex(__version__, r'^\d+\.\d+\.\d+$')
        for name in ('README.md','RELEASE_NOTES.md','CHANGELOG.md','QUICKSTART-SK.txt','docs/TEST-RESULTS.md'):
            self.assertIn(__version__, (ROOT/name).read_text(encoding='utf-8'),name)
        self.assertEqual(subprocess.check_output([sys.executable,'-m','resolve_edit_tracker','--version'],cwd=ROOT,text=True).strip(),'Stintory '+__version__)
    def test_no_private_release_numbers(self):
        old = re.compile(r'\b' + r'1\.' + r'5\.(?:\d+|x|X)\b')
        for file,rel in entries():
            self.assertIsNone(old.search(rel.as_posix()),str(rel))
            if file.suffix.lower() not in {'.png','.ico'}:
                self.assertIsNone(old.search(file.read_text(encoding='utf-8')),str(rel))
