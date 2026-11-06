import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import installer


class SetupLogTests(unittest.TestCase):
    def test_log_tail_handles_ansi_and_carriage_return_progress(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(installer,'DATA',Path(folder)):
            (Path(folder)/'setup-bgm.log').write_text('\x1b[32mDownloading model.npz\x1b[0m\n10%\r40%\r100%\n',encoding='utf-8')
            result=installer.log_tail('bgm')
            self.assertEqual(result['lines'],['Downloading model.npz','10%','40%','100%'])
            self.assertLess(abs(time.time()-result['updatedAt']),5)
            self.assertEqual(installer.log_tail('../settings')['lines'],[])
            self.assertEqual(installer.log_tail('translation')['lines'],[])

    def test_logs_are_bounded_and_unicode_safe(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(installer,'DATA',Path(folder)):
            (Path(folder)/'setup-song.log').write_text('시작\n'+'x'*100000+'\n'+''.join(f'파일 {n} 설치\n' for n in range(100)),encoding='utf-8')
            lines=installer.log_tail('song')['lines']
            self.assertEqual(len(lines),40)
            self.assertEqual(lines[-1],'파일 99 설치')
            self.assertLessEqual(sum(map(len,lines)),20000)

    def test_status_exposes_elapsed_and_quiet_time(self):
        state={'active':True,'state':'installing','component':'bgm','startedAt':70,'componentStartedAt':80}
        with patch.object(installer,'STATE',state),patch.object(installer.time,'time',return_value=100),patch.object(installer,'log_tail',return_value={'lines':['file.npz'],'updatedAt':90}):
            status=installer.status()
            self.assertEqual(status['elapsedSeconds'],30)
            self.assertEqual(status['quietSeconds'],10)
            self.assertEqual(status['log']['lines'],['file.npz'])
