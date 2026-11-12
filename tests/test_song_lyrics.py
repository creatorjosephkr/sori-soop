import unittest
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
import engine
from song_lyrics import check_lyric_tokens,check_audio_codes,check_formatted_lyric_tokens

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

    def test_instrumental_ignores_existing_lyrics_and_vocal_language(self):
        from app import validate
        settings=validate({'policy':'manual','mode':'song','model':'ace-step','backend':'cpu','seconds':30,'instrumental':True})
        with tempfile.TemporaryDirectory() as tmp,patch.object(engine,'DATA',Path(tmp)),patch.object(engine,'ready',return_value=True),patch.object(threading.Thread,'start'):
            try:
                for lyrics in ('', '기존 보컬 가사'):
                    job=engine.start(settings,'Soft piano ballad',8,lyrics=lyrics,language='ko')
                    self.assertEqual(job['lyrics'],'')
                    self.assertEqual(job['language'],'unknown')
                    self.assertTrue(job['settings']['instrumental'])
                    engine.ACTIVE=None
                with self.assertRaisesRegex(ValueError,'가사'):
                    engine.start({**settings,'instrumental':False},'Soft piano ballad',8)
            finally:engine.ACTIVE=None;engine.CURRENT=None

    def test_instrumental_requires_boolean_option_and_manual_duration(self):
        from app import validate
        settings={'policy':'manual','mode':'song','model':'ace-step','backend':'cpu','seconds':30,'instrumental':True}
        with self.assertRaisesRegex(ValueError,'길이'):
            validate({**settings,'durationMode':'auto','seconds':None})
        with self.assertRaisesRegex(ValueError,'Instrumental'):
            validate({**settings,'instrumental':'false'})

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

    def test_actual_encoder_lyric_input_cannot_be_silently_cut(self):
        def tokenizer(text,**kwargs):
            self.assertFalse(kwargs['truncation'])
            return {'input_ids':[0]*2049}
        with self.assertRaisesRegex(ValueError,'2,048'):
            check_formatted_lyric_tokens(tokenizer,'# Languages\nko\n# Lyric\nlast verse')

    def test_runner_uses_upstream_lm_guidance_and_turbo_shift(self):
        root=Path(__file__).resolve().parent.parent
        runner=(root/'runners/song.py').read_text(encoding='utf-8')
        self.assertIn("temperature=expert['lmTemperature'],cfg_scale=expert['lmCfgScale'],top_p=expert['lmTopP']",runner)
        self.assertIn("inference_steps=expert['inferenceSteps'],shift=expert['shift']",runner)
        import song_expert
        self.assertEqual((song_expert.DEFAULTS['lmTemperature'],song_expert.DEFAULTS['lmCfgScale'],song_expert.DEFAULTS['lmTopP'],song_expert.DEFAULTS['inferenceSteps'],song_expert.DEFAULTS['shift']),(0.85,2.0,0.9,8,3.0))

    def test_lyric_request_prompt_contains_acestep_g2p_and_syllable_rules(self):
        root=Path(__file__).resolve().parent.parent
        script=(root/'web/app.js').read_text(encoding='utf-8')
        for phrase in (
            "당신은 AI 음악 생성 모델 'ACE-Step' 전용 작사가이자 프롬프트 엔지니어입니다.",
            "1. **음절 수 엄격 제한 (가사 누락 방지)**",
            "2. **한국어 발음 최적화 (G2P 표기 적용)**",
            "display_lyrics(화면 표시용 정자법 가사)와 phonetic_lyrics(ACE-Step 엔진 전달용 발음 가사)를 각각 생성하여 제공",
            "3. **구조 태그 및 호흡 기호 배치**",
            "4. **ACE-Step 영문 스타일 프롬프트 세팅**",
            "### [곡 기획 정보]",
        ):
            self.assertIn(phrase,script)
