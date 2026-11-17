"""Regression tests for startup failures and no-input return to Resolve."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from resolve_edit_tracker import probe, models
from resolve_edit_tracker.state import AppState
from resolve_edit_tracker.store import SessionStore

class StartupRecovery(unittest.TestCase):
    def test_reacquires_stale_empty_project_proxy(self):
        stale=object(); ready=object(); dvr=NS(scriptapp=Mock(side_effect=[stale,ready]))
        empty={"running":True,"apiOk":True,"page":None,"project":None}
        active={"running":True,"apiOk":True,"page":"edit","project":"P","timeline":"T"}
        sent=[]
        def emit(data):
            sent.append(data.copy())
            if data.get('project'): raise KeyboardInterrupt
        with patch.object(probe,'resolve_running',return_value=True),patch.object(probe,'setup_env',return_value=(dvr,None)),patch.object(probe,'resolve_version',return_value='21'),patch.object(probe,'snapshot',side_effect=lambda obj:dict(empty if obj is stale else active)),patch.object(probe,'emit',side_effect=emit),patch.object(probe.time,'sleep'):
            with self.assertRaises(KeyboardInterrupt): probe.main()
        self.assertEqual(dvr.scriptapp.call_count,2)
        self.assertEqual(len(sent),6)
        self.assertEqual(sent[-1]['project'],'P')

    def test_repeated_null_connection_recycles_helper(self):
        dvr=NS(scriptapp=Mock(return_value=None))
        with patch.object(probe,'resolve_running',return_value=True),patch.object(probe,'setup_env',return_value=(dvr,None)),patch.object(probe,'emit') as emit,patch.object(probe.time,'sleep'):
            probe.main()
        self.assertEqual(emit.call_count,6)
        self.assertEqual(dvr.scriptapp.call_count,6)
        self.assertTrue(all(not c.args[0]['apiOk'] for c in emit.call_args_list))

    def test_repeated_required_api_failures_recycle_helper(self):
        dvr=NS(scriptapp=Mock(return_value=object()))
        with patch.object(probe,'resolve_running',return_value=True),patch.object(probe,'setup_env',return_value=(dvr,None)),patch.object(probe,'resolve_version',return_value='21'),patch.object(probe,'snapshot',side_effect=probe.ApiCompatibilityError('bad proxy')),patch.object(probe,'emit') as emit,patch.object(probe.time,'sleep'):
            probe.main()
        self.assertEqual(emit.call_count,6)
        self.assertGreaterEqual(dvr.scriptapp.call_count,2)
        self.assertTrue(all(not c.args[0]['apiOk'] for c in emit.call_args_list))

    def test_short_startup_error_does_not_prevent_recovery(self):
        dvr=NS(scriptapp=Mock(side_effect=[None,None,object()]))
        calls=[]
        def emit(data):
            calls.append(data.copy())
            if data.get('project'): raise KeyboardInterrupt
        with patch.object(probe,'resolve_running',return_value=True),patch.object(probe,'setup_env',return_value=(dvr,None)),patch.object(probe,'resolve_version',return_value='21'),patch.object(probe,'snapshot',return_value={'running':True,'apiOk':True,'page':'edit','project':'P'}),patch.object(probe,'emit',side_effect=emit),patch.object(probe.time,'sleep'):
            with self.assertRaises(KeyboardInterrupt): probe.main()
        self.assertEqual([c['apiOk'] for c in calls],[False,False,True])

    def test_return_to_resolve_without_mouse_movement(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=[1_800_000_000.0]; idle=[12.0]; foreground=[(22,'explorer.exe')]
            state=AppState(store=SessionStore(tmp),clock=lambda:clock[0],idle_fn=lambda:idle[0],foreground_fn=lambda:foreground[0],own_pid=999,toast_fn=lambda **_:None,autostart_get=lambda:False,autostart_set=lambda *_:False)
            state.update_settings(trackOnlyWhenFrontmost=True,idleMinutes=5)
            s=models.ResolveStatus(running=True,api_ok=True,page='edit',project='P',timeline='T')
            for _ in range(8):
                clock[0]+=1; state.handle(s,models.CONNECTED); state.tick()
            self.assertEqual(state.state,models.IDLE_PAUSED)
            foreground[0]=(33,'resolve.exe'); clock[0]+=1; state.tick()
            self.assertEqual(state.state,models.TRACKING)
            self.assertEqual(state.current.project,'P')
            self.assertEqual(idle[0],12)
            self.assertEqual(state.current.duration_sec,0)
            clock[0]+=1; state.tick(); self.assertEqual(state.current.duration_sec,1)

    def test_away_does_not_resume_if_idle_limit_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=[1_800_000_000.0]; idle=[400.0]
            state=AppState(store=SessionStore(tmp),clock=lambda:clock[0],idle_fn=lambda:idle[0],foreground_fn=lambda:(33,'resolve.exe'),own_pid=999,toast_fn=lambda **_:None,autostart_get=lambda:False,autostart_set=lambda *_:False)
            state.update_settings(trackOnlyWhenFrontmost=True,idleMinutes=5)
            state.status=models.ResolveStatus(running=True,api_ok=True,page='edit',project='P',timeline='T');state.connection=models.CONNECTED;state.state=models.IDLE_PAUSED;state.idle_pause_reason='away'
            clock[0]+=1;state.tick();self.assertEqual(state.state,models.IDLE_PAUSED);self.assertIsNone(state.current)
