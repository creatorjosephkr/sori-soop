import unittest
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
import engine
from song_lyrics import check_lyric_tokens,check_audio_codes

class SongLyricsTests(unittest.TestCase):
    def test_all_sections_and_descriptions_remain_in_lyrics_even_with_legacy_setting(self):
        original='[intro]\n(잔잔한 피아노 연주)\n[Verse 1]\n첫 번째 줄\n(함께 불러요)\n[Chorus]\n마지막 줄\n[outro]\n(Piano fades out)'
        with tempfile.TemporaryDirectory() as tmp,patch.object(engine,'DATA',Path(tmp)),patch.object(engine,'ready',return_value=True),patch.object(engine.translation,'ready',return_value=False),patch.object(threading.Thread,'start'):
            try:
                job=engine.start({'mode':'song','model':'ace-step','backend':'cpu','seconds':30,'instrumentalEdges':True},'Soft piano ballad',8,lyrics=original)
                self.assertEqual(job['lyrics'],original)
                self.assertEqual(job['prompt'],'Soft piano ballad')
                for field in ('generationLyrics','lyricDirections','generationInputPrompt'):self.assertNotIn(field,job)
            finally:engine.ACTIVE=None;engine.CURRENT=None

    def test_translation_does_not_merge_lyrics_or_legacy_arrangement_field(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(engine,'DATA',Path(tmp)),patch.object(engine.subprocess,'Popen') as launch:
            job={'id':'e'*32,'prompt':'Warm piano','lyrics':'[Intro]\n한글 연주 설명','generationInputPrompt':'Warm piano\n한글 연주 설명','settings':{'mode':'song'}}
            self.assertTrue(engine.translate_job(job))
            launch.assert_not_called()
            self.assertNotIn('generationPrompt',job)
            self.assertEqual(job['lyrics'],'[Intro]\n한글 연주 설명')

    def test_token_overflow_and_incomplete_audio_codes_are_explicit_errors(self):
        tokenizer=lambda text,**kw:{'input_ids':list(range(2049))}
        with self.assertRaisesRegex(ValueError,'2,048'):check_lyric_tokens(tokenizer,'긴 가사','ko')
        self.assertEqual(check_lyric_tokens(lambda *a,**k:{'input_ids':[1]*2048},'가사','ko'),2048)
        with self.assertRaisesRegex(ValueError,'끝까지'):check_audio_codes('<|audio_code_1|>'*100,100)
        self.assertEqual(check_audio_codes('<|audio_code_1|>'*500,100),500)
