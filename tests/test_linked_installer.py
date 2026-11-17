import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from setup_linked import configure

class LinkedInstallerTests(unittest.TestCase):
    def test_unicode_paths_and_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'Priečinok používateľa'
            root.mkdir()
            exe = root / 'Python 3.12' / 'python.exe'
            exe.parent.mkdir()
            exe.with_name('pythonw.exe').touch()
            for name in ('link_resolve.ps1','make_shortcut.vbs','launch_with_resolve.vbs','run_tracker.pyw','launch_resolve.pyw'):
                (root/name).touch()
            calls=[]
            with patch("linked_task.user_sid",return_value="S-1-5-21-42"):
                configure(root, exe, root/'Windows', lambda stage, args: calls.append(args))
            self.assertEqual(len(calls),4)
            self.assertIn("/XML",calls[3])
            self.assertEqual(calls[1][-1],str(exe.with_name('pythonw.exe')))
            self.assertEqual(calls[1][-3],str(root/'link_resolve.ps1'))
            self.assertEqual((root/'launch-mode.txt').read_text().strip(),'linked')
    def test_missing_pythonw_does_not_write_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(FileNotFoundError):
                configure(root,root/'python.exe',root,lambda *_: self.fail('unexpected call'))
            self.assertFalse((root/'launch-mode.txt').exists())
