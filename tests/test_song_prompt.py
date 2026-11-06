import json
from pathlib import Path
import tempfile
import threading
import time
import sys
import unittest
from unittest.mock import patch
import engine
from song_lyrics import check_caption_tokens

class SongPromptTests(unittest.TestCase):
    def test_token_boundary_is_exact_and_never_truncates(self):
        for count in (256,257):
            def tokenizer(text,**kwargs):
                self.assertIs(kwargs['truncation'],False)
                self.assertIn('# Instruction',text)
                return {'input_ids':[1]*count}
            text='# Instruction\nfill\n# Caption\n'+('long '*120)
            if count==256:self.assertEqual(check_caption_tokens(tokenizer,text),256)
            else:
                with self.assertRaisesRegex(ValueError,'257토큰.*1토큰 초과'):check_caption_tokens(tokenizer,text)

    def test_song_over_512_characters_is_accepted_before_token_validation(self):
        prompt='Expressive instrumental texture with warm melodic phrasing. '*12
        self.assertGreater(len(prompt),512)
        with tempfile.TemporaryDirectory() as tmp,patch.object(engine,'DATA',Path(tmp)),patch.object(engine,'ready',return_value=True),patch.object(threading.Thread,'start'):
            try:
                job=engine.start({'mode':'song','model':'ace-step','backend':'cpu','seconds':30},prompt,8,lyrics='[Verse]\nSing every line')
                self.assertEqual(job['prompt'],prompt.strip())
            finally:engine.ACTIVE=None;engine.CURRENT=None

    def test_long_translation_is_not_rejected_at_512_and_bgm_limit_stays(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(engine,'DATA',Path(tmp)):
            job={'id':'f'*32,'prompt':'긴 음악 설명','settings':{'mode':'song'}};engine.save(job)
            translated='Expressive warm piano. '*35
            def process(*a,**k):
                (Path(tmp)/'jobs'/(job['id']+'.translation.json')).write_text(json.dumps({'text':translated,'model':'test','revision':'test'}))
                class P:
                    def wait(self,timeout):return 0
                return P()
            with patch.object(engine.subprocess,'Popen',side_effect=process):self.assertTrue(engine.translate_job(job))
            self.assertEqual(job['generationPrompt'],translated)
            job['prompt']='x'*2001;job['settings']['mode']='bgm'
            with self.assertRaises(ValueError):engine.translate_job(job)

    def test_token_failure_is_shown_as_the_main_result_message(self):
        script_text="""import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--progress');a,_=p.parse_known_args()
Path(a.progress.replace('.progress.json','.input-check.json')).write_text(json.dumps({'ok':False,'error':'설명이 256토큰을 초과했습니다: 270토큰'}),encoding='utf-8')
sys.exit(1)
"""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'probe.py';script.write_text(script_text,encoding='utf-8')
            with patch.object(engine,'DATA',root),patch.object(engine,'ready',return_value=True),patch.object(engine,'song_paths',return_value=(root,Path(sys.executable),script)):
                job=engine.start({'mode':'song','model':'ace-step','backend':'cpu','seconds':30},'piano',8,lyrics='Sing every line')
                deadline=time.monotonic()+10
                while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.02)
                self.assertIsNone(engine.ACTIVE)
                self.assertEqual(job['status'],'failed')
                self.assertIn('270토큰',job['error'])
                self.assertNotIn('엔진 실행에 실패',job['error'])
