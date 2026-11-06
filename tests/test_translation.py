import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import engine
import translation

class TextTranslationTests(unittest.TestCase):
    def test_mixed_prompt_preserves_english_presets_and_spacing(self):
        original='  따뜻한 피아노. Gentle drums.\n\nStyle: lofi, no vocals.'
        calls=[]
        def translate(text):calls.append(text);return 'Warm piano.'
        self.assertEqual(translation.translate_segments(original,translate),'  Warm piano. Gentle drums.\n\nStyle: lofi, no vocals.')
        self.assertEqual(calls,['따뜻한 피아노.'])
        self.assertEqual(translation.translate_segments('Warm piano',lambda _:self.fail()),'Warm piano')
    def test_chunking_keeps_every_token_and_eos_without_truncation(self):
        tokens=['▁word' if i%3==0 else str(i) for i in range(1500)]
        chunks=translation.token_chunks(tokens)
        self.assertEqual([token for chunk in chunks for token in chunk[:-1]],tokens)
        self.assertTrue(all(len(chunk)<=193 and chunk[-1]=='</s>' for chunk in chunks))
    def test_empty_or_still_korean_translation_is_not_accepted(self):
        for result in ['','아직 한글']:
            with self.assertRaises(ValueError):translation.translate_segments('차분한 음악',lambda _:result)
    def test_missing_translator_rejects_korean_before_job_start(self):
        settings={'mode':'bgm','model':'small-music','backend':'cpu','seconds':10,'policy':'manual'}
        with patch.object(translation,'ready',return_value=False):
            with self.assertRaisesRegex(ValueError,'번역 모델'):engine.start(settings,'차분한 음악',8)

class TranslationJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.data=patch.object(engine,'DATA',self.root);self.data.start()
        self.job={'id':'f'*32,'prompt':'차분한 음악','title':'나의 제목','lyrics':'원래 가사','status':'queued','settings':{'mode':'song'}}
        engine.save(self.job)
    def tearDown(self):
        engine.PROCESS=None;self.data.stop();self.tmp.cleanup()
    def process(self,*args,**kwargs):
        # Write what the real offline translator would produce; music isn't loaded yet.
        (self.root/'jobs'/(self.job['id']+'.translation.json')).write_text(json.dumps({'text':'Calm piano music.','model':translation.MODEL_ID,'revision':translation.REVISION}), encoding='utf-8')
        class Process:
            def wait(self,timeout):return 0
        return Process()
    def test_translates_caption_only_and_finishes_process_before_music(self):
        with patch.object(engine.subprocess,'Popen',side_effect=self.process) as launch:
            self.assertTrue(engine.translate_job(self.job))
        self.assertEqual(self.job['prompt'],'차분한 음악')
        self.assertEqual(self.job['lyrics'],'원래 가사')
        self.assertEqual(self.job['title'],'나의 제목')
        self.assertEqual(self.job['generationPrompt'],'Calm piano music.')
        self.assertIsNone(engine.PROCESS)
        self.assertEqual(launch.call_args.kwargs['env']['HF_HUB_OFFLINE'],'1')
        self.assertEqual(json.loads((self.root/'jobs'/(self.job['id']+'.json')).read_text(encoding='utf-8'))['generationPrompt'],'Calm piano music.')
    def test_translation_failure_does_not_silently_use_korean(self):
        with patch.object(engine.subprocess,'Popen') as launch:
            launch.return_value.wait.return_value=1
            with self.assertRaisesRegex(ValueError,'번역에 실패'):engine.translate_job(self.job)
        self.assertNotIn('generationPrompt',self.job);self.assertIsNone(engine.PROCESS)
    def test_cancel_stops_before_music_and_english_bypasses_translation(self):
        self.job['cancelRequested']=True
        with patch.object(engine.subprocess,'Popen') as launch:
            self.assertFalse(engine.translate_job(self.job));launch.assert_not_called()
        self.job['prompt']='Gentle piano'
        with patch.object(engine.subprocess,'Popen') as launch:
            self.assertTrue(engine.translate_job(self.job));launch.assert_not_called()

    def test_cancel_terminates_running_translation(self):
        started=threading.Event();stopped=threading.Event();result=[]
        class Process:
            def wait(self,timeout):
                started.set()
                if not stopped.wait(2):raise AssertionError('translation not cancelled')
                return -15
            def poll(self):return None
            def terminate(self):stopped.set()
        with patch.object(engine,'ACTIVE',self.job['id']),patch.object(engine,'CURRENT',self.job),patch.object(engine.subprocess,'Popen',return_value=Process()):
            thread=threading.Thread(target=lambda:result.append(engine.translate_job(self.job)))
            thread.start();self.assertTrue(started.wait(2));engine.cancel();thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(result,[False]);self.assertTrue(self.job['cancelRequested']);self.assertIsNone(engine.PROCESS)
