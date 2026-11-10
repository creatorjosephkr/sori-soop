import json
import io
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

import exaone_lyrics


class ExaoneLyricsTests(unittest.TestCase):
    def test_parse_json_response_clean(self):
        sample = {
            "title": "비 내리는 밤",
            "stylePrompt": "ballad, emotional piano, female vocal, 72 BPM",
            "displayLyrics": "창밖에 비가 내려요",
            "lyrics": "[ko]\n[Verse 1]\n창바케 비가 내려요",
            "summary": "비 오는 밤의 위로",
        }
        parsed = exaone_lyrics.parse_json_response(json.dumps(sample, ensure_ascii=False))
        self.assertEqual(parsed["title"], "비 내리는 밤")
        self.assertEqual(parsed["lyrics"], "[ko]\n[Verse 1]\n창바케 비가 내려요")

    def test_parse_json_response_in_markdown_fence(self):
        raw = """여기 요청하신 가사입니다:
```json
{
  "title": "새벽의 멜로디",
  "stylePrompt": "lofi, soft piano, 80 BPM",
  "lyrics": "[ko]\n[Intro]\n라라라"
}
```
좋은 하루 되세요!"""
        parsed = exaone_lyrics.parse_json_response(raw)
        self.assertEqual(parsed["title"], "새벽의 멜로디")
        self.assertIn("라라라", parsed["lyrics"])

    def test_parse_broken_json_with_quotes(self):
        # Unescaped quotes inside lyrics that would normally break json.loads
        broken = """
{
  "title": "따뜻한 고백",
  "stylePrompt": "ballad, acoustic piano",
  "displayLyrics": "[Verse 1]\\n"사랑해"라고 혼잣말을 했어",
  "lyrics": "[ko]\\n[Verse 1]\\n"사랑해"라고 혼잔마를 해써",
  "summary": "고백의 순간",
}
"""
        parsed = exaone_lyrics.parse_json_response(broken)
        self.assertEqual(parsed["title"], "따뜻한 고백")
        self.assertIn("혼잔마를 해써", parsed["lyrics"])

    def test_parse_markdown_text_fallback(self):
        markdown_text = """
<think>
사용자가 비 오는 날 가사를 원한다.
</think>

안녕하세요! 요청하신 가사를 작성했습니다.

### [곡 제목]: 비 내리는 버스 정류장
### [영문 스타일 프롬프트]: emotional ballad, acoustic piano, 72 BPM
### [정음 가사]:
[Verse 1]
창밖에 비가 내려요
기다림이 길어지네요

[Chorus]
따뜻한 커피 한 잔에
하루를 묻어둡니다

### [G2P 발음 표기 가사]:
[ko]
[Verse 1]
창바케 비가 내려요
기다리미 길어지네요

[Chorus]
따뜨탄 커피 한 자네
하루를 무더둠니다

### [곡 구성 요약]:
비 내리는 정류장에서 느끼는 위로
"""
        parsed = exaone_lyrics.parse_json_response(markdown_text)
        self.assertEqual(parsed["title"], "비 내리는 버스 정류장")
        self.assertIn("emotional ballad", parsed["stylePrompt"])
        self.assertIn("창바케 비가 내려요", parsed["lyrics"])
        self.assertIn("창밖에 비가 내려요", parsed["standardLyrics"])

    def test_empty_api_key_or_prompt(self):
        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics.generate_lyrics("", "주제")
        self.assertIn("API 키", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics.generate_lyrics("test_key", "   ")
        self.assertIn("주제", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "달빛 아래서",
                        "stylePrompt": "acoustic pop, acoustic guitar, male vocal, 95 BPM",
                        "displayLyrics": "달빛이 내려앉은 길",
                        "lyrics": "[Verse 1]\n달비치 내려안즌 길",
                        "summary": "달빛 아래 산책 이야기",
                    })
                }
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = exaone_lyrics.generate_lyrics(
            api_key="valid-key",
            prompt="달밤 산책",
            genre="어쿠스틱",
            mood="따뜻함",
            voice="남성",
            tempo="보통",
        )
        self.assertEqual(res["title"], "달빛 아래서")
        self.assertTrue(res["lyrics"].startswith("[ko]\n"))
        self.assertEqual(res["standardLyrics"], "달빛이 내려앉은 길")
        self.assertEqual(res["stylePrompt"], "acoustic pop, acoustic guitar, male vocal, 95 BPM")

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_fallback_reasoning_content(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning_content": json.dumps({
                        "title": "새벽 별",
                        "stylePrompt": "lofi, 80 BPM",
                        "displayLyrics": "별이 빛나는 밤",
                        "lyrics": "[Verse 1]\n벼리 빈나는 밤",
                        "summary": "새벽 별 이야기",
                    }),
                },
                "finish_reason": "stop",
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = exaone_lyrics.generate_lyrics(api_key="valid-key", prompt="새벽 별")
        self.assertEqual(res["title"], "새벽 별")
        self.assertTrue(res["lyrics"].startswith("[ko]\n"))

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_empty_finish_reason_length(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning_content": "",
                },
                "finish_reason": "length",
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics.generate_lyrics(api_key="valid-key", prompt="가을")
        self.assertIn("토큰 한도", str(ctx.exception))

    def test_sanitize_title_reasoning_leakage(self):
        leaked = '"가을의 온기" maybe. DisplayLyrics with structure tags. Lyrics with [ko] first. Need blank lines between sections.'
        clean = exaone_lyrics.sanitize_title(leaked, default_topic="가을")
        self.assertEqual(clean, "가을의 온기")

        leaked_no_quote = '가을의 온기" maybe. DisplayLyrics with structure tags.'
        clean_no_quote = exaone_lyrics.sanitize_title(leaked_no_quote, default_topic="가을")
        self.assertEqual(clean_no_quote, "가을의 온기")

        pure_thought = "Let's draft sections. Count: 1 2 3 4"
        clean_thought = exaone_lyrics.sanitize_title(pure_thought, default_topic="가을 이야기")
        self.assertEqual(clean_thought, "가을 이야기")

    def test_sanitize_lyrics_reasoning_leakage(self):
        leaked = """We need generate lyrics in Korean. Need G2P conversions: e.g. 빛나는 -> 빈나는.
Avoid tricky. But need G2P. Since lyrics field should use pronunciation.
[ko]
[Verse 1]
가을 바람 불면 잠시 멈춰
낙엽 진 길 천천히 걸어가"""
        sanitized = exaone_lyrics.sanitize_lyrics(leaked)
        self.assertTrue(sanitized.startswith("[ko]\n[Verse 1]"))
        self.assertNotIn("We need generate", sanitized)
        self.assertIn("가을 바람 불면", sanitized)

    def test_sanitize_lyrics_same_line_tag(self):
        raw = "[ko] [Verse 1]\n가을 바람에 낙엽이 지고"
        sanitized = exaone_lyrics.sanitize_lyrics(raw)
        self.assertTrue(sanitized.startswith("[ko]\n[Verse 1]"))

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_rejects_raw_reasoning_without_json(self, mock_urlopen):
        # When content is empty and reasoning_content is just text without JSON
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning_content": "Title: '가을의 온기' maybe. We need generate lyrics in Korean...",
                },
                "finish_reason": "stop",
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics.generate_lyrics(api_key="valid-key", prompt="가을")
        self.assertIn("유효한 가사 결과", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_salvages_song_from_reasoning_when_content_empty_or_empty_dict(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": "{}",
                    "reasoning_content": """We need craft lyrics. Title: '가을 낙엽'.
[Verse 1]
가을 바람이 불어와 낙엽이 흩날리네
따뜻한 차 한 잔에 마음을 녹여요
[Chorus]
계절이 바뀌어도 우리의 기억은
여전히 따스하게 남아있어요
""",
                },
                "finish_reason": "stop",
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = exaone_lyrics.generate_lyrics(api_key="valid-key", prompt="가을 낙엽")
        self.assertEqual(res["title"], "가을 낙엽")
        self.assertIn("가을 바람이 불어와", res["lyrics"])
        self.assertIn("가을 바람이 불어와", res["standardLyrics"])

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_korean_keys(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "제목": "커피 향기",
                        "스타일": "acoustic folk, acoustic guitar, 80 BPM",
                        "정음가사": "[Verse 1]\n따뜻한 커피를 마시며\n창밖을 바라봐요",
                        "발음가사": "[ko]\n[Verse 1]\n따뜨탄 커피를 마시며\n창바클 바라봐요",
                        "요약": "커피 한 잔의 여유",
                    })
                }
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = exaone_lyrics.generate_lyrics(api_key="valid-key", prompt="커피")
        self.assertEqual(res["title"], "커피 향기")
        self.assertIn("따뜨탄 커피를", res["lyrics"])
        self.assertIn("따뜻한 커피를", res["standardLyrics"])
        self.assertEqual(res["stylePrompt"], "acoustic folk, acoustic guitar, 80 BPM")

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_snake_case_keys(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "가을 바람",
                        "style_prompt": "indie pop, piano, 85 BPM",
                        "display_lyrics": "[Verse 1]\n바람이 살며시 불어와",
                        "g2p_lyrics": "[ko]\n[Verse 1]\n바라미 살며시 부러와",
                    })
                }
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = exaone_lyrics.generate_lyrics(api_key="valid-key", prompt="가을 바람")
        self.assertEqual(res["title"], "가을 바람")
        self.assertIn("부러와", res["lyrics"])
        self.assertIn("불어와", res["standardLyrics"])

    def test_sanitize_lyrics_preserves_song_lines_with_english_words(self):
        raw = """[ko]
[Verse 1]
Maybe 너를 사랑했나 봐
우린 너무 오랫동안 (too long) 기다려왔어
가을 바람이 시원하게 불어와
"""
        sanitized = exaone_lyrics.sanitize_lyrics(raw)
        self.assertIn("Maybe 너를 사랑했나 봐", sanitized)
        self.assertIn("우린 너무 오랫동안", sanitized)
        self.assertIn("가을 바람이 시원하게", sanitized)

    def test_sanitize_lyrics_strips_syllable_counters(self):
        raw = """[ko]
[Verse 1]
가을 바람이 불어와
Count: 가(1) 을(2) 바(3) 람(4) 이(5) too long. Need 6-10 syllables. Shorten:
따뜻한 커피를 마셔요
"""
        sanitized = exaone_lyrics.sanitize_lyrics(raw)
        self.assertIn("가을 바람이 불어와", sanitized)
        self.assertIn("따뜻한 커피를 마셔요", sanitized)
        self.assertNotIn("Count:", sanitized)
        self.assertNotIn("too long", sanitized)

    @patch("urllib.request.urlopen")
    def test_test_api_key_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"choices": []}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        self.assertTrue(exaone_lyrics.test_api_key("test-key"))

    @patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            url="https://api.exaone.ai", code=401, msg="Unauthorized", hdrs={}, fp=io.BytesIO(b"")
        ),
    )
    def test_api_key_unauthorized(self, mock_urlopen):
        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics.test_api_key("bad-key")
        self.assertIn("401", str(ctx.exception))

    def test_get_timeout_seconds(self):
        # Default is 600s
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(exaone_lyrics.get_timeout_seconds(), 600)
            self.assertEqual(exaone_lyrics.get_timeout_seconds(300), 300)
            self.assertEqual(exaone_lyrics.get_timeout_seconds("900"), 900)
            self.assertIsNone(exaone_lyrics.get_timeout_seconds(0))
            self.assertIsNone(exaone_lyrics.get_timeout_seconds("0"))
            self.assertIsNone(exaone_lyrics.get_timeout_seconds("none"))
            self.assertIsNone(exaone_lyrics.get_timeout_seconds("unlimited"))

        # From environment variable
        with patch.dict("os.environ", {"EXAONE_TIMEOUT": "0"}):
            self.assertIsNone(exaone_lyrics.get_timeout_seconds())
        with patch.dict("os.environ", {"EXAONE_TIMEOUT": "900"}):
            self.assertEqual(exaone_lyrics.get_timeout_seconds(), 900)
        with patch.dict("os.environ", {"EXAONE_TIMEOUT": "none"}):
            self.assertIsNone(exaone_lyrics.get_timeout_seconds())

    @patch("urllib.request.urlopen")
    def test_execute_chat_completion_timeout_error(self, mock_urlopen):
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")
        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics._execute_chat_completion("http://test", {}, "key", 600)
        self.assertIn("600초", str(ctx.exception))
        self.assertIn("응답 시간이 초과", str(ctx.exception))

        # When timeout is None (unlimited), message still clearly states timeout occurred without sec
        with self.assertRaises(ValueError) as ctx:
            exaone_lyrics._execute_chat_completion("http://test", {}, "key", None)
        self.assertIn("응답 시간이 초과", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_generate_lyrics_english(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "Midnight Coffee",
                        "stylePrompt": "pop, acoustic guitar, female vocal, 105 BPM",
                        "displayLyrics": "[Verse 1]\nRaindrops falling on the street\nWarm coffee makes me complete",
                        "lyrics": "[Verse 1]\nRaindrops falling on the street\nWarm coffee makes me complete",
                        "summary": "비 오는 밤 따뜻한 커피 한 잔의 여유",
                    })
                }
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = exaone_lyrics.generate_lyrics(
            api_key="valid-key",
            prompt="coffee in rainy night",
            genre="어쿠스틱",
            language="en",
        )
        self.assertEqual(res["title"], "Midnight Coffee")
        self.assertEqual(res["language"], "en")
        self.assertTrue(res["lyrics"].startswith("[en]\n"))
        self.assertIn("Raindrops falling", res["standardLyrics"])
        self.assertNotIn("[en]", res["standardLyrics"])
        self.assertEqual(res["stylePrompt"], "pop, acoustic guitar, female vocal, 105 BPM")

    def test_sanitize_lyrics_english(self):
        raw = "[Verse 1]\nMaybe we were meant to fly\nAcross the open summer sky"
        sanitized = exaone_lyrics.sanitize_lyrics(raw, language="en")
        self.assertTrue(sanitized.startswith("[en]\n[Verse 1]"))
        self.assertIn("Maybe we were meant to fly", sanitized)

    def test_sanitize_title_english(self):
        leaked = '"Summer Sunset" maybe. DisplayLyrics with structure tags.'
        clean = exaone_lyrics.sanitize_title(leaked, default_topic="Sunset", language="en")
        self.assertEqual(clean, "Summer Sunset")


class ExaoneHttpTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        import app

        self.app = app
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, "DATA", Path(self.tmp.name))
        self.patch.start()
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        import threading

        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.patch.stop()
        self.tmp.cleanup()

    def test_settings_save_api_key(self):
        body = {"policy": "auto", "mode": "song", "exaoneApiKey": "test-exa-key-1234"}
        req = urllib.request.Request(
            self.base + "/api/settings",
            json.dumps(body).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(data["settings"]["exaoneApiKey"], "test-exa-key-1234")

        with urllib.request.urlopen(self.base + "/api/status") as resp:
            status = json.load(resp)
            self.assertTrue(status.get("hasExaoneApiKey"))

    def test_settings_save_timeout(self):
        # Save custom timeout (e.g. 0 for unlimited, or 900 for 15min)
        body = {"policy": "auto", "mode": "song", "exaoneTimeout": 0}
        req = urllib.request.Request(
            self.base + "/api/settings",
            json.dumps(body).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(data["settings"]["exaoneTimeout"], 0)

        with urllib.request.urlopen(self.base + "/api/status") as resp:
            status = json.load(resp)
            self.assertEqual(status.get("exaoneTimeout"), 0)

        # Save 900s
        body["exaoneTimeout"] = 900
        req = urllib.request.Request(
            self.base + "/api/settings",
            json.dumps(body).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(data["settings"]["exaoneTimeout"], 900)

        with urllib.request.urlopen(self.base + "/api/status") as resp:
            status = json.load(resp)
            self.assertEqual(status.get("exaoneTimeout"), 900)

    @patch("exaone_lyrics.generate_lyrics")
    def test_lyrics_generate_endpoint(self, mock_gen):
        mock_gen.return_value = {
            "title": "테스트 곡",
            "stylePrompt": "ballad, 70 BPM",
            "displayLyrics": "안녕",
            "lyrics": "[ko]\n[Verse 1]\n안녕",
            "summary": "요약",
        }
        body = {
            "apiKey": "temp-key",
            "prompt": "가을 여행",
            "genre": "발라드",
            "timeout": 0,
        }
        req = urllib.request.Request(
            self.base + "/api/lyrics/generate",
            json.dumps(body).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data["ok"])
            self.assertEqual(data["data"]["title"], "테스트 곡")
            mock_gen.assert_called_once_with(
                api_key="temp-key",
                prompt="가을 여행",
                genre="발라드",
                mood="",
                voice="",
                tempo="",
                timeout=0,
                language="ko",
            )

    @patch("exaone_lyrics.generate_lyrics")
    def test_lyrics_generate_endpoint_english(self, mock_gen):
        mock_gen.return_value = {
            "title": "Autumn Song",
            "stylePrompt": "pop, 100 BPM",
            "displayLyrics": "Hello world",
            "lyrics": "[en]\n[Verse 1]\nHello world",
            "summary": "영어 가사",
            "language": "en",
        }
        body = {
            "apiKey": "temp-key",
            "prompt": "autumn story",
            "language": "en",
        }
        req = urllib.request.Request(
            self.base + "/api/lyrics/generate",
            json.dumps(body).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data["ok"])
            self.assertEqual(data["data"]["title"], "Autumn Song")
            self.assertEqual(data["data"]["language"], "en")
            mock_gen.assert_called_once_with(
                api_key="temp-key",
                prompt="autumn story",
                genre="",
                mood="",
                voice="",
                tempo="",
                timeout=None,
                language="en",
            )


if __name__ == "__main__":
    unittest.main()
