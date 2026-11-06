import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import engine
import installer


class AutoInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data=Path(self.tmp.name)
        for target,value in [('DATA',self.data),('STATE',{'active':False,'component':None,'state':'idle','error':None}),('PROCESS',None)]:
            p=patch.object(installer,target,value);p.start();self.addCleanup(p.stop)
        self.ready={'bgm':False,'translation':False,'song':False}
        p=patch.object(installer,'status',side_effect=lambda:{**installer.STATE,'ready':dict(self.ready)})
        self.status_patch=p;p.start();self.addCleanup(p.stop)
        p=patch.object(installer.shutil,'disk_usage');self.disk=p.start();self.disk.return_value.free=100*1024**3;self.addCleanup(p.stop)

    def test_queue_is_sequential_and_complete(self):
        def complete(component):self.ready[component]=True
        with patch.object(installer,'run',side_effect=complete) as run:
            installer.STATE['active']=True
            installer.run_queue(['bgm','translation','song'])
            self.assertEqual([c.args[0] for c in run.call_args_list],['bgm','translation','song'])
        self.assertEqual(installer.STATE['state'],'completed');self.assertFalse(installer.active())
        self.assertIsNone(installer.saved_error())

    def test_auto_skips_ready_and_duplicate_starts(self):
        self.ready['bgm']=True
        with patch.object(engine,'ACTIVE',None),patch.object(installer,'uv_path',return_value='uv'),patch.object(installer.threading,'Thread') as thread:
            installer.start('auto')
            self.assertEqual(thread.call_args.kwargs['args'],(['translation','song'],))
            installer.start('auto');self.assertEqual(thread.call_count,1)

    def test_failure_stops_queue_persists_and_needs_manual_retry(self):
        with patch.object(installer,'run',side_effect=RuntimeError('offline')) as run:
            installer.run_queue(['bgm','translation','song']);self.assertEqual(run.call_count,1)
        self.assertEqual(installer.saved_error(),'offline');self.assertEqual(installer.STATE['state'],'failed')
        with patch.object(installer.threading,'Thread') as thread:
            installer.start('auto');thread.assert_not_called()
        with patch.object(engine,'ACTIVE',None),patch.object(installer,'uv_path',return_value='uv'),patch.object(installer.threading,'Thread') as thread:
            installer.start('all');thread.assert_called_once();self.assertIsNone(installer.saved_error())

    def test_disk_shortage_and_cancel_do_not_start_more_components(self):
        self.disk.return_value.free=2*1024**3
        with patch.object(installer,'run') as run:
            installer.run_queue(['bgm','song']);run.assert_not_called()
        self.assertIn('저장 공간',installer.saved_error())
        installer.STATE.update(state='cancelled',active=True)
        with patch.object(installer,'run') as run:
            installer.run_queue(['song']);run.assert_not_called()
        self.assertFalse(installer.active())

    def test_persisted_failure_is_restored_after_restart(self):
        installer.remember('offline')
        self.status_patch.stop()
        with patch.object(engine,'ready',return_value=False):
            self.assertEqual(installer.status()['state'],'failed')
            self.assertEqual(installer.status()['error'],'offline')
