import importlib.util
import json
import math
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
from pathlib import Path
from unittest.mock import patch

import app
import audio_export
import engine


def sample_wav(path, channels=2, rate=48000):
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b''.join(struct.pack('<h', int(8000*math.sin(i*2*math.pi*440/rate)))*channels for i in range(rate)))


@unittest.skipUnless(importlib.util.find_spec('lameenc'), 'Install desktop dependencies for MP3 export tests')
class Mp3ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = patch.object(engine, 'DATA', self.root)
        self.patch.start()
        (self.root/'audio').mkdir()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def make_result(self, ident, mode='bgm', channels=2, rate=48000):
        engine.save({'id': ident, 'status': 'completed', 'createdAt': 1, 'settings': {'mode': mode}})
        source = self.root/'audio'/(ident+'.wav')
        sample_wav(source, channels, rate)
        return source

    def test_real_mp3_for_all_modes_cache_and_delete(self):
        import soundfile as sf
        for mode, ident, channels, rate in [('bgm', 'a'*32, 2, 48000), ('song', 'b'*32, 2, 44100), ('sfx', 'c'*32, 1, 32000)]:
            with self.subTest(mode=mode):
                source = self.make_result(ident, mode, channels, rate)
                original = source.read_bytes()
                target = engine.export_mp3(ident)
                info = sf.info(str(target))
                self.assertEqual(info.format, 'MP3')
                self.assertEqual(info.channels, channels)
                self.assertEqual(info.samplerate, rate)
                self.assertAlmostEqual(info.duration, 1, delta=.15)
                self.assertEqual(source.read_bytes(), original)
                with patch.object(audio_export, 'write_mp3') as convert:
                    self.assertEqual(engine.export_mp3(ident), target)
                    convert.assert_not_called()
                engine.delete_result(ident)
                self.assertFalse(target.exists())
                self.assertTrue((self.root/'trash'/ident/target.name).is_file())
                with self.assertRaises(FileNotFoundError):engine.export_mp3(ident)

    def test_failed_conversion_is_atomic_and_retryable(self):
        ident = 'd'*32
        source = self.make_result(ident)
        target = source.with_suffix('.mp3')
        with patch('lameenc.Encoder') as encoder:
            encoder.return_value.encode.side_effect = RuntimeError('encoding failed')
            with self.assertRaises(RuntimeError):engine.export_mp3(ident)
        self.assertFalse(target.exists())
        self.assertEqual(list(source.parent.glob('*.tmp')), [])
        self.assertGreater(engine.export_mp3(ident).stat().st_size, 0)

    def test_incomplete_result_and_invalid_ids_are_rejected(self):
        ident = 'e'*32
        self.make_result(ident)
        engine.save({'id': ident, 'status': 'running'})
        with self.assertRaises(ValueError):engine.export_mp3(ident)
        for bad in ('../settings', '', None):
            with self.assertRaises(ValueError):engine.export_mp3(bad)

    def test_http_mime_range_and_conversion_error(self):
        ident = 'f'*32
        self.make_result(ident)
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/audio/{ident}.mp3'
        try:
            with urllib.request.urlopen(url) as response:
                self.assertEqual(response.headers['Content-Type'], 'audio/mpeg')
                payload = response.read()
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Range': 'bytes=0-19'})) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), payload[:20])
            with patch.object(engine, 'export_mp3', side_effect=RuntimeError('encoder unavailable')):
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(url)
                self.assertEqual(error.exception.code, 503)
                self.assertIn('MP3', json.load(error.exception)['error'])
                error.exception.close()
        finally:
            server.shutdown();server.server_close()
