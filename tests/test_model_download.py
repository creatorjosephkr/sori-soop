import logging
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from model_download import DownloadWatchdog,materialize,AnonymousNotice


class ModelDownloadTests(unittest.TestCase):
    def test_idle_download_times_out_but_activity_resets_watchdog(self):
        stalled=threading.Event();now=[0];ticks=iter((5,9,18,20))
        with patch('model_download.time.monotonic',side_effect=lambda:now[0]):
            watchdog=DownloadWatchdog(stalled.set,idle_seconds=10)
            def tick(_):
                now[0]=next(ticks)
                if now[0]==9:watchdog.touch()
                return False
            with patch.object(watchdog.stop,'wait',side_effect=tick) as wait:
                watchdog.run()
            self.assertTrue(stalled.is_set())
            self.assertEqual(now[0],20)
            self.assertEqual(wait.call_count,4)

    def test_normal_completion_stops_watchdog(self):
        stalled=threading.Event()
        with DownloadWatchdog(stalled.set,idle_seconds=60):pass
        self.assertFalse(stalled.wait(.1))

    def test_place_model_and_repair_broken_link(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'download';source.write_bytes(b'weights')
            target=Path(folder)/'models'/'model.npz';target.parent.mkdir()
            try:target.symlink_to(Path(folder)/'missing')
            except OSError:pass
            materialize(source,target);self.assertEqual(target.read_bytes(),b'weights')
            self.assertFalse(list(target.parent.glob('*.pending')))

    def test_copy_fallback_preserves_complete_file(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(Path,'symlink_to',side_effect=OSError),patch('model_download.os.link',side_effect=OSError):
            source=Path(folder)/'source';source.write_bytes(b'weights')
            target=Path(folder)/'models'/'model.npz'
            materialize(source,target);self.assertFalse(target.is_symlink());self.assertEqual(target.read_bytes(),b'weights')

    def test_notice_is_explained_and_real_errors_are_kept(self):
        notice=AnonymousNotice()
        record=logging.LogRecord('hf',30,'',1,'Warning: You are sending unauthenticated requests to the HF Hub.',(),None)
        self.assertTrue(notice.filter(record));self.assertIn('로그인 없이',record.getMessage())
        record=logging.LogRecord('hf',40,'',1,'HTTP 429 too many requests',(),None)
        notice.filter(record);self.assertEqual(record.getMessage(),'HTTP 429 too many requests')
