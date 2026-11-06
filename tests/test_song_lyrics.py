import unittest
from song_lyrics import prepare,check_lyric_tokens,check_audio_codes

class SongLyricsTests(unittest.TestCase):
    def test_instrumental_descriptions_are_separate_and_vocal_lines_stay_in_order(self):
        original='[인트로]\n(잔잔한 피아노 연주)\n[Verse 1]\n첫 번째 줄\n(함께 불러요)\n[Chorus]\n마지막 줄\n[Outro]\n피아노가 잦아든다'
        result=prepare(original)
        self.assertEqual(result['lyrics'],'[Intro]\n[Verse 1]\n\n첫 번째 줄\n(함께 불러요)\n[Chorus]\n\n마지막 줄\n[Outro]')
        self.assertEqual([d['text'] for d in result['directions']],['잔잔한 피아노 연주','피아노가 잦아든다'])
        self.assertIn('잔잔한 피아노',original)

    def test_vocal_intro_opt_out_and_same_line_lyrics_are_preserved(self):
        original='[Intro]\n처음 노래해\n[Verse] 이어 노래해\n[Outro]\n끝을 노래해'
        result=prepare(original,False)
        self.assertEqual(result['directions'],[])
        for line in ('처음 노래해','이어 노래해','끝을 노래해'):self.assertIn(line,result['lyrics'])
        with self.assertRaises(ValueError):prepare('[Intro]\n피아노 연주\n[Outro]')

    def test_token_overflow_and_incomplete_audio_codes_are_explicit_errors(self):
        tokenizer=lambda text,**kw:{'input_ids':list(range(2049))}
        with self.assertRaisesRegex(ValueError,'2,048'):check_lyric_tokens(tokenizer,'긴 가사','ko')
        self.assertEqual(check_lyric_tokens(lambda *a,**k:{'input_ids':[1]*2048},'가사','ko'),2048)
        with self.assertRaisesRegex(ValueError,'끝까지'):check_audio_codes('<|audio_code_1|>'*100,100)
        self.assertEqual(check_audio_codes('<|audio_code_1|>'*500,100),500)
