import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import engine

SCRIPT = '''import argparse,time,wave
p=argparse.ArgumentParser()
p.add_argument('--out');p.add_argument('--seconds',type=int)
a,_=p.parse_known_args()
time.sleep(.3)
with wave.open(a.out,'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(8000)
 w.writeframes(b'\\0'*(a.seconds*8000*4))
'''

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.script=self.root/'fake.py';self.script.write_text(SCRIPT, encoding='utf-8')
        self.patch1=patch.object(engine,'DATA',self.root);self.patch1.start()
        self.patch2=patch.object(engine,'engine_paths',return_value=(self.root,Path(sys.executable),self.script));self.patch2.start()
        self.settings={'mode':'bgm','model':'small-music','backend':'cpu','seconds':10,'policy':'manual'}
    def wait(self):
        deadline=time.monotonic()+5
        while engine.ACTIVE and time.monotonic()<deadline: time.sleep(.02)
        self.assertIsNone(engine.ACTIVE)
    def tearDown(self):
        engine.cancel();self.wait();self.patch1.stop();self.patch2.stop();self.tmp.cleanup()
    def test_generated_wav_and_durable_metadata(self):
        job=engine.start(self.settings,'piano',4,title='햇살이 머무는 아침')
        with self.assertRaises(ValueError): engine.start(self.settings,'another',4)
        self.wait()
        saved=json.loads((self.root/'jobs'/(job['id']+'.json')).read_text(encoding='utf-8'))
        self.assertEqual(saved['status'],'completed')
        self.assertEqual(saved['title'],'햇살이 머무는 아침')
        self.assertEqual(saved['durationSeconds'],10)
        self.assertEqual(saved['seed'],job['seed'])
    def test_cancel_and_retry(self):
        engine.start(self.settings,'piano',4);engine.cancel();self.wait()
        self.assertEqual(engine.history()[0]['status'],'cancelled')
        engine.start(self.settings,'piano',4);self.wait()
        self.assertEqual(engine.history()[0]['status'],'completed')
    def test_insufficient_memory_and_empty_prompt(self):
        for prompt,memory in [('piano',1),('',4)]:
            with self.assertRaises(ValueError): engine.start(self.settings,prompt,memory)

class DeleteResultTests(unittest.TestCase):
    def test_remove_result_and_files_to_trash(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine,'DATA',Path(tmp)):
            ident='a'*32
            engine.save({'id':ident,'status':'completed','createdAt':1})
            audio=Path(tmp)/'audio';audio.mkdir()
            (audio/(ident+'.wav')).write_bytes(b'music')
            log=Path(tmp)/'jobs'/(ident+'.log');log.write_text('log', encoding='utf-8')
            engine.delete_result(ident)
            self.assertEqual(engine.history(),[])
            self.assertFalse((audio/(ident+'.wav')).exists())
            self.assertFalse(log.exists())
            self.assertEqual((Path(tmp)/'trash'/ident/(ident+'.wav')).read_bytes(),b'music')
            with self.assertRaises(FileNotFoundError):engine.delete_result(ident)

    def test_reject_active_and_invalid_paths(self):
        with patch.object(engine,'ACTIVE','b'*32):
            for ident in ['b'*32,'../../settings',None]:
                with self.assertRaises(ValueError):engine.delete_result(ident)

class SongTests(unittest.TestCase):
    def test_lyrics_and_language_required_before_start(self):
        settings={'policy':'manual','mode':'song','model':'ace-step','backend':'cpu','seconds':30}
        for lyrics,language in [('', 'ko'), ('가사', 'invalid'), ('가'*4001, 'ko')]:
            with self.assertRaises(ValueError):
                engine.start(settings,'gentle pop',8,lyrics,language)

    def test_song_request_preserves_lyrics_language_and_seed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine,'DATA',Path(tmp)), patch.object(engine,'ready',return_value=True), patch.object(threading.Thread,'start'):
            settings={'policy':'manual','mode':'song','model':'ace-step','backend':'cpu','seconds':30}
            lyrics='[Verse]\n오늘도 노래해\n[Chorus]\n너와 함께 걸어가'
            try:
                job=engine.start(settings,'gentle pop',8,lyrics,'ko')
                saved=json.loads((Path(tmp)/'jobs'/(job['id']+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(saved['lyrics'],lyrics)
                self.assertEqual(saved['language'],'ko')
                self.assertEqual(saved['settings']['mode'],'song')
                self.assertEqual(saved['seed'],job['seed'])
            finally:
                engine.ACTIVE=None;engine.CURRENT=None

class HistoryPaginationTests(unittest.TestCase):
    def test_history_keeps_results_older_than_first_hundred(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine,'DATA',Path(tmp)):
            for index in range(103):
                engine.save({'id':f'{index:032x}','createdAt':index,'status':'completed','settings':{'mode':'bgm'}})
            items=engine.history()
            self.assertEqual(len(items),103)
            self.assertEqual(items[0]['createdAt'],102)
            self.assertEqual(items[-1]['createdAt'],0)

class TitleTests(unittest.TestCase):
    def test_invalid_title_rejected_before_model_start(self):
        settings={'mode':'bgm','model':'small-music','backend':'cpu','seconds':10,'policy':'manual'}
        for title in (None,{},'가'*101):
            with self.assertRaises(ValueError):engine.start(settings,'piano',8,title=title)

class GenerationFailureTests(unittest.TestCase):
    def test_windows_native_exit_codes_keep_their_meaning(self):
        for code in (0xC000012D,0xC000012D-2**32,0xC0000017):
            message,details=engine.generation_failure(code,'loading model',windows=True)
            self.assertIn('가상 메모리',message)
            self.assertIn(f'0x{code & 0xffffffff:08X}',details)
        message,details=engine.generation_failure(0xC0000005,'loading model',windows=True)
        self.assertIn('메모리 접근 오류',message)
        self.assertNotIn('부족',message)
        self.assertIn('0xC0000005',details)

    def test_tail_preserves_multiline_failure_without_unbounded_history(self):
        log='private old text\n'+'\n'.join(f'line {n}' for n in range(100))+'\n\x1b[31mRuntimeError: not enough memory\x1b[0m'
        message,details=engine.generation_failure(1,log)
        self.assertIn('메모리를 확보',message)
        self.assertIn('line 99\nRuntimeError:',details)
        self.assertNotIn('private old text',details)
        self.assertNotIn('\x1b',details)
        self.assertLess(len(details),12100)

class WindowsSongStagesTests(unittest.TestCase):
    def test_planner_exits_before_render_and_failure_does_not_start_render(self):
        probe='''import argparse,json,os,sys,wave
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--phase');p.add_argument('--request');p.add_argument('--out');a,_=p.parse_known_args()
r=Path(a.request);job=json.loads(r.read_text());stages=r.with_suffix('.stages')
with stages.open('a') as f:f.write(a.phase+' '+str(os.getpid())+'\\n')
if a.phase=='plan':sys.exit(2 if job['prompt']=='fail' else 0)
previous=stages.read_text().splitlines();assert len(previous)==2
assert previous[0].split()[1]!=previous[1].split()[1]
with wave.open(a.out,'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(8000);w.writeframes(bytes(10*8000*4))
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'probe.py';script.write_text(probe)
            with patch.object(engine,'DATA',root),patch.object(engine,'ready',return_value=True),patch.object(engine,'song_paths',return_value=(root,Path(sys.executable),script)),patch.object(engine.platform,'system',return_value='Windows'):
                for prompt,expected in [('piano','completed'),('fail','failed')]:
                    job=engine.start({'mode':'song','model':'ace-step','backend':'cpu','seconds':10},prompt,16,lyrics='New lyrics')
                    deadline=time.monotonic()+10
                    while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.02)
                    self.assertIsNone(engine.ACTIVE)
                    self.assertEqual(job['status'],expected,job.get('error'))
                    phases=(root/'jobs'/job['id']).with_suffix('.stages').read_text().splitlines()
                    self.assertEqual(len(phases),2 if expected=='completed' else 1)
