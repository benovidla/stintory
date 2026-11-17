import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from resolve_edit_tracker import probe, models


def fixture(page='edit', timeline=True, count=1):
    tl=NS(GetName=lambda:'Timeline',GetCurrentTimecode=lambda:'01:00:00:00') if timeline else None
    proj=NS(GetName=lambda:'Project',GetCurrentTimeline=lambda:tl,GetTimelineCount=lambda:count,IsRenderingInProgress=lambda:True)
    pm=NS(GetCurrentProject=lambda:proj)
    resolve=NS(GetCurrentPage=lambda:page,GetProjectManager=lambda:pm,GetVersionString=lambda:'21.1.0')
    return resolve,proj,tl

class Compatibility(unittest.TestCase):
    def test_current_and_future_version_not_gated(self):
        for version in ['19.0','21.1.0','99.0.1']:
            r,p,t=fixture();r.GetVersionString=lambda:version
            self.assertEqual(probe.resolve_version(r),version)
            self.assertTrue(models.ResolveStatus.from_dict(probe.snapshot(r)).in_project)
    def test_old_version_method_fallback(self):
        r,_,_=fixture();del r.GetVersionString;r.GetVersion=lambda:[22,3,1,5,'beta']
        self.assertEqual(probe.resolve_version(r),'22.3.1.5')
        del r.GetVersion;self.assertIsNone(probe.resolve_version(r))
    def test_optional_methods_removed(self):
        r,p,t=fixture();del p.GetTimelineCount,p.IsRenderingInProgress,t.GetCurrentTimecode
        data=probe.snapshot(r);self.assertEqual(data['timeline'],'Timeline');self.assertFalse(data['rendering']);self.assertIsNone(data['timecode'])
        self.assertTrue(models.ResolveStatus.from_dict(data).in_project)
    def test_required_method_removed(self):
        for obj,method in [('r','GetCurrentPage'),('r','GetProjectManager'),('p','GetName'),('p','GetCurrentTimeline'),('t','GetName')]:
            r,p,t=fixture();delattr({'r':r,'p':p,'t':t}[obj],method)
            with self.assertRaisesRegex(probe.ApiCompatibilityError,method):probe.snapshot(r)
    def test_required_proxy_stub_throws(self):
        r,p,t=fixture()
        def missing():raise RuntimeError('native stub')
        p.GetCurrentTimeline=missing
        with self.assertRaises(probe.ApiCompatibilityError):probe.snapshot(r)
    def test_unexpected_response_not_billed(self):
        r,p,t=fixture();t.GetName=lambda:123
        with self.assertRaises(probe.ApiCompatibilityError):probe.snapshot(r)
    def test_unknown_page_pauses(self):
        r,p,t=fixture('FuturePage');data=probe.snapshot(r)
        self.assertEqual(data['page'],'futurepage');self.assertFalse(models.ResolveStatus.from_dict(data).in_project)
    def test_manager_page_pauses(self):
        r,p,t=fixture(None);self.assertFalse(models.ResolveStatus.from_dict(probe.snapshot(r)).in_project)
    def test_empty_project_not_billed(self):
        r,p,t=fixture(timeline=False,count=0);self.assertIsNone(probe.snapshot(r)['project'])
        del p.GetTimelineCount;self.assertIsNone(probe.snapshot(r)['project'])
    def test_existing_project_without_current_timeline(self):
        r,p,t=fixture(timeline=False,count=2);self.assertEqual(probe.snapshot(r)['project'],'Project')
    def test_no_project_after_prior_snapshot(self):
        r,p,t=fixture();self.assertEqual(probe.snapshot(r)['project'],'Project');r.GetProjectManager=lambda:NS(GetCurrentProject=lambda:None)
        self.assertIsNone(probe.snapshot(r)['project'])
    def test_page_case_and_version_protocol(self):
        r,_,_=fixture('EDIT');d=probe.snapshot(r);d['resolveVersion']='21.1';s=models.ResolveStatus.from_dict(d)
        self.assertTrue(s.in_project);self.assertEqual(s.resolve_version,'21.1')

if __name__=='__main__':unittest.main()
