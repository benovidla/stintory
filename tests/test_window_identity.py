import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from pathlib import Path
from resolve_edit_tracker import winapi, ui_common
from PIL import Image

class WindowIdentityTests(unittest.TestCase):
    def test_windows_identity_passed_to_shell_before_windows(self):
        fn=Mock(return_value=0)
        with patch.object(winapi,'IS_WIN',True), patch.object(winapi,'ctypes',SimpleNamespace(windll=SimpleNamespace(shell32=SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=fn)),c_long=int),create=True), patch.object(winapi,'wintypes',SimpleNamespace(LPCWSTR=str),create=True):
            self.assertTrue(winapi.set_app_identity())
            fn.assert_called_once_with('Stintory.Desktop')
            fn.return_value=-1
            self.assertFalse(winapi.set_app_identity())

    def test_non_windows_no_identity(self):
        with patch.object(winapi,'IS_WIN',False): self.assertFalse(winapi.set_app_identity())

    def test_native_icon_asset_and_fallback(self):
        win=Mock()
        with patch.object(winapi,'IS_WIN',True): ui_common.set_window_icon(win)
        path=Path(win.iconbitmap.call_args.kwargs['default'])
        self.assertTrue(path.exists())
        with Image.open(path) as image:
            self.assertTrue({(16,16),(32,32),(48,48)}.issubset(image.ico.sizes()))
        win.iconbitmap.side_effect=ui_common.tk.TclError('test')
        with patch.object(winapi,'IS_WIN',True),patch.object(ui_common,'tk_photo',return_value='photo'):
            ui_common.set_window_icon(win)
        win.iconphoto.assert_called_once_with(True,'photo')

    def test_project_manager_title_conservative(self):
        for title in ('Project Manager','DaVinci Resolve Project Manager'):
            self.assertTrue(winapi.is_project_manager_title(title))
        for title in ('DaVinci Resolve Studio 21','DaVinci Resolve 20.1'):
            self.assertTrue(winapi.is_project_manager_title(title,owned=True))
            self.assertFalse(winapi.is_project_manager_title(title,owned=False))
        for title in ('Demo Project','DaVinci Resolve Studio 21 - Demo Project','Preferences','', 'Project Manager demo'):
            self.assertFalse(winapi.is_project_manager_title(title,owned=True))
        with patch.object(winapi,'IS_WIN',False): self.assertFalse(winapi.project_manager_frontmost())

if __name__=='__main__': unittest.main()
