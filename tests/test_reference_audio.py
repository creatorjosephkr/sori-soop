import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app
import engine


class ReferenceAudioEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_list_resolve_and_delete(self):
        with patch.object(engine, 'DATA', self.data):
            item = engine.save_reference_audio('보컬 샘플.wav', b'RIFFdemo')
            self.assertEqual(item['name'], '보컬 샘플.wav')
            self.assertEqual(item['ext'], '.wav')
            self.assertEqual(item['size'], 8)
            self.assertTrue(item['audioUrl'].startswith('/reference-audio/'))

            items = engine.list_reference_audios()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['id'], item['id'])

            path, meta = engine.resolve_reference_audio_path(item['id'])
            self.assertEqual(meta['id'], item['id'])
            self.assertEqual(path.read_bytes(), b'RIFFdemo')

            engine.delete_reference_audio(item['id'])
            self.assertEqual(engine.list_reference_audios(), [])
            with self.assertRaises(FileNotFoundError):
                engine.resolve_reference_audio_path(item['id'])

    def test_save_rejects_empty_and_bad_extension(self):
        with patch.object(engine, 'DATA', self.data):
            with self.assertRaises(ValueError):
                engine.save_reference_audio('sample.wav', b'')
            with self.assertRaises(ValueError):
                engine.save_reference_audio('notes.txt', b'abc')

    def test_start_attaches_reference_audio_to_song_job(self):
        settings = {
            'policy': 'manual',
            'mode': 'song',
            'model': 'ace-step',
            'backend': 'cpu',
            'seconds': 30,
            'durationMode': 'manual',
            'instrumental': False,
            'songQuality': 'light',
            'peakDb': -8,
        }
        with patch.object(engine, 'DATA', self.data), \
             patch.object(engine, 'ready', return_value=True), \
             patch.object(engine, 'run'):
            item = engine.save_reference_audio('singer.mp3', b'ID3demo')
            job = engine.start(
                settings,
                'Warm acoustic ballad',
                available=16,
                lyrics='[Verse]\nHello world',
                language='en',
                reference_audio_id=item['id'],
            )
            self.assertEqual(job['referenceAudioId'], item['id'])
            self.assertEqual(job['referenceAudioName'], 'singer.mp3')
            self.assertEqual(Path(job['referenceAudioPath']).read_bytes(), b'ID3demo')
            with engine.GUARD:
                engine.ACTIVE = None
                engine.CURRENT = None

    def test_start_attaches_up_to_two_reference_audios(self):
        settings = {
            'policy': 'manual',
            'mode': 'song',
            'model': 'ace-step',
            'backend': 'cpu',
            'seconds': 30,
            'durationMode': 'manual',
            'instrumental': False,
            'songQuality': 'light',
            'peakDb': -8,
        }
        with patch.object(engine, 'DATA', self.data), \
             patch.object(engine, 'ready', return_value=True), \
             patch.object(engine, 'run'):
            item1 = engine.save_reference_audio('singer1.wav', b'RIFF1')
            item2 = engine.save_reference_audio('singer2.wav', b'RIFF2')
            item3 = engine.save_reference_audio('singer3.wav', b'RIFF3')
            job = engine.start(
                settings,
                'Duet acoustic ballad',
                available=16,
                lyrics='[Verse 1]\nHi\n[Verse 2]\nHello',
                language='en',
                reference_audio_ids=[item1['id'], item2['id'], item1['id']],
            )
            self.assertEqual(job['referenceAudioIds'], [item1['id'], item2['id']])
            self.assertEqual(job['referenceAudioNames'], ['singer1.wav', 'singer2.wav'])
            self.assertEqual(job['referenceAudioName'], 'singer1.wav, singer2.wav')
            self.assertEqual(len(job['referenceAudioPaths']), 2)
            with engine.GUARD:
                engine.ACTIVE = None
                engine.CURRENT = None
            with self.assertRaises(ValueError):
                engine.start(
                    settings,
                    'Too many refs',
                    available=16,
                    lyrics='[Verse]\nHi',
                    language='en',
                    reference_audio_ids=[item1['id'], item2['id'], item3['id']],
                )

    def test_start_rejects_reference_audio_outside_song_mode(self):
        settings = {
            'policy': 'manual',
            'mode': 'bgm',
            'model': 'small-music',
            'backend': 'cpu',
            'seconds': 20,
            'peakDb': -8,
        }
        with patch.object(engine, 'DATA', self.data):
            item = engine.save_reference_audio('singer.wav', b'RIFFdemo')
            with self.assertRaises(ValueError):
                engine.start(settings, 'Piano', available=16, reference_audio_id=item['id'])


class ReferenceAudioHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_upload_list_serve_and_delete_endpoints(self):
        with patch.object(engine, 'DATA', self.data):
            req = urllib.request.Request(
                self.base + '/api/reference-audio',
                data=b'RIFFtest-audio',
                headers={'X-File-Name': urllib.parse.quote('가수 샘플.wav')},
                method='POST',
            )
            with urllib.request.urlopen(req) as res:
                self.assertEqual(res.status, 201)
                created = json.load(res)['item']
            self.assertEqual(created['name'], '가수 샘플.wav')

            with urllib.request.urlopen(self.base + '/api/reference-audio') as res:
                items = json.load(res)['items']
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['id'], created['id'])

            with urllib.request.urlopen(self.base + created['audioUrl']) as res:
                self.assertEqual(res.status, 200)
                self.assertEqual(res.read(), b'RIFFtest-audio')

            del_req = urllib.request.Request(
                self.base + '/api/reference-audio/delete',
                data=json.dumps({'id': created['id']}).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(del_req) as res:
                self.assertEqual(json.load(res), {'ok': True})

            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(self.base + created['audioUrl'])
            self.assertEqual(err.exception.code, 404)
            err.exception.close()

    def test_generate_endpoint_forwards_reference_audio_id(self):
        with patch.object(engine, 'DATA', self.data), \
             patch.object(app, 'diagnose', return_value={'appleSilicon': False, 'availableGB': 16, 'gpu': []}), \
             patch.object(app, 'resolve_generation_settings', side_effect=lambda s, _i: s), \
             patch.object(engine, 'start', return_value={'id': 'a' * 32, 'settings': {'mode': 'song'}}) as start_mock:
            body = {
                'settings': {
                    'policy': 'manual',
                    'mode': 'song',
                    'model': 'ace-step',
                    'backend': 'cpu',
                    'seconds': 30,
                    'durationMode': 'manual',
                },
                'prompt': 'Acoustic ballad',
                'lyrics': '[Verse]\nHello',
                'language': 'en',
                'referenceAudioId': 'b' * 32,
                'referenceAudioIds': ['b' * 32, 'c' * 32],
            }
            req = urllib.request.Request(
                self.base + '/api/generate',
                data=json.dumps(body).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req) as res:
                self.assertEqual(res.status, 202)
            self.assertEqual(start_mock.call_args.kwargs['reference_audio_id'], 'b' * 32)
            self.assertEqual(start_mock.call_args.kwargs['reference_audio_ids'], ['b' * 32, 'c' * 32])
