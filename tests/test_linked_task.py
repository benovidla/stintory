import importlib.machinery
import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
import linked_task
from resolve_edit_tracker.__main__ import main

class LinkedTaskTests(unittest.TestCase):
    def test_xml_interactive_limited_indefinite_unicode(self):
        root=Path('C:/Users/Žofia/Apps & Tools/Stintory')
        doc=ET.fromstring(linked_task.task_xml(root,root/'Python'/'pythonw.exe','S-1-5-21-123',datetime(2026,11,17,12)))
        ns={'t':linked_task.NS}
        def text(path):return doc.findtext(path, namespaces=ns)
        self.assertEqual(text('.//t:Interval'),'PT1M')
        self.assertIsNone(doc.find('.//t:Duration',ns))
        self.assertEqual(text('.//t:LogonType'),'InteractiveToken')
        self.assertEqual(text('.//t:RunLevel'),'LeastPrivilege')
        self.assertEqual(text('.//t:MultipleInstancesPolicy'),'IgnoreNew')
        self.assertEqual(text('.//t:ExecutionTimeLimit'),'PT0S')
        self.assertEqual(text('.//t:WorkingDirectory'),str(root))
        self.assertIn('Žofia',text('.//t:Arguments'))
        self.assertEqual(text('.//t:Command'),str(root/'Python'/'pythonw.exe'))
        self.assertIn('--scheduled --with-resolve',text('.//t:Arguments'))
        self.assertTrue(text('.//t:Arguments').startswith('-E '))
        self.assertEqual(text('.//t:WakeToRun'),'false')
    def test_no_resolve_no_ui_or_mutex(self):
        for result in (False,None):
            with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=result),patch('resolve_edit_tracker.winapi.acquire_single_instance') as mutex:
                main(['--scheduled','--with-resolve']);mutex.assert_not_called()
    def test_scheduled_duplicate_no_panel(self):
        with patch('resolve_edit_tracker.winapi.resolve_process_running',return_value=True),patch('resolve_edit_tracker.winapi.acquire_single_instance',return_value=False),patch('resolve_edit_tracker.__main__.signal_dir') as signals:
            main(['--scheduled','--with-resolve']);signals.assert_not_called()
    def test_shortcut_launch_unicode_and_flags(self):
        loader=importlib.machinery.SourceFileLoader('launch_resolve',str(Path(__file__).resolve().parents[1]/'launch_resolve.pyw'))
        spec=importlib.util.spec_from_loader(loader.name,loader);mod=importlib.util.module_from_spec(spec);loader.exec_module(mod)
        with tempfile.TemporaryDirectory(prefix='Žofia ') as d:
            root=Path(d);resolve=root/'Resolve.exe';py=root/'pythonw.exe';resolve.touch();py.touch()
            (root/'launcher-config.txt').write_text(f'{resolve}\n{py}\n --foo\n{root}\n',encoding='utf-16')
            popen=Mock();mod.launch(root,popen)
            self.assertEqual(popen.call_count,2)
            self.assertIn('--foo',popen.call_args_list[0].args[0]);self.assertEqual(popen.call_args_list[1].args[0], [str(py),'-E',str(root/'run_tracker.pyw'),'--with-resolve','--wait-resolve','--linked-launch'])
    def test_scheduled_running_starts_ui(self):
        with patch("resolve_edit_tracker.winapi.resolve_process_running",return_value=True),patch("resolve_edit_tracker.winapi.acquire_single_instance",return_value=True),patch("resolve_edit_tracker.app.TrackerApp") as app:
            main(["--scheduled","--with-resolve"])
            app.assert_called_once_with(simulate=False,use_tray=True,with_resolve=True,background=False,offline=False,manual=False)
            app.return_value.run.assert_called_once()
    def test_sid_parsing(self):
        with patch('linked_task.subprocess.check_output',return_value=b'"machine\\name","S-1-5-21-123"\r\n'):
            self.assertEqual(linked_task.user_sid(Path('C:/Windows')),'S-1-5-21-123')
