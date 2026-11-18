import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import wave
from pathlib import Path
from unittest.mock import patch

import app
import engine


def _write_wav(path: Path, seconds: float, rate: int = 8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(seconds * rate))
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x01\x00' * (frames * 2))


def _create_source_song(root: Path, ident='a' * 32, duration=40.0, seed=123456, audio_codes='<|audio_code_1|>', with_composition=True):
    wav_path = root / 'audio' / f'{ident}.wav'
    _write_wav(wav_path, duration)
    job = {
        'id': ident,
        'createdAt': 1000.0,
        'status': 'completed',
        'title': '봄날의 산책',
        'prompt': 'warm acoustic guitar, gentle female vocal, 100 BPM',
        'lyrics': '[Verse]\n햇살이 비추는 거리\n[Chorus]\n함께 걸어가요',
        'language': 'ko',
        'seed': seed,
        'settings': {
            'policy': 'manual',
            'mode': 'song',
            'model': 'ace-step',
            'backend': 'cpu',
            'seconds': int(duration),
            'durationMode': 'manual',
            'songQuality': 'light',
            'peakDb': -8,
        },
        'durationSeconds': duration,
        'audioUrl': f'/audio/{ident}.wav',
    }
    if with_composition:
        job['composition'] = {
            'metadata': {'bpm': 100, 'keyscale': 'C major', 'timesignature': '4', 'language': 'ko'},
            'audioCodes': audio_codes,
        }
    engine.save(job)
    return job


class ValidateEditSpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = patch.object(engine, 'DATA', self.root)
        self.patch.start()
        self.src = _create_source_song(self.root)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_repaint_section_validation_and_bounds(self):
        spec, src = engine.validate_edit_spec({
            'mode': 'repaint',
            'subMode': 'section',
            'sourceJobId': self.src['id'],
            'repaintStart': 10.0,
            'repaintEnd': 22.5,
            'repaintMode': 'balanced',
            'repaintStrength': 0.5,
        })
        self.assertEqual(src['id'], self.src['id'])
        self.assertEqual(spec['repaintStart'], 10.0)
        self.assertEqual(spec['repaintEnd'], 22.5)
        self.assertEqual(spec['targetDuration'], 40.0)
        self.assertIn('00:10~00:22', spec['summaryLabel'])

        with self.assertRaises(ValueError):
            engine.validate_edit_spec({'mode': 'repaint', 'subMode': 'section', 'sourceJobId': self.src['id'], 'repaintStart': 10, 'repaintEnd': 11})
        with self.assertRaises(ValueError):
            engine.validate_edit_spec({'mode': 'repaint', 'subMode': 'section', 'sourceJobId': self.src['id'], 'repaintStart': 30, 'repaintEnd': 20})
        with self.assertRaises(ValueError):
            engine.validate_edit_spec({'mode': 'repaint', 'subMode': 'section', 'sourceJobId': self.src['id'], 'repaintStart': 10, 'repaintEnd': 45})

    def test_repaint_extend_validation(self):
        spec, _ = engine.validate_edit_spec({
            'mode': 'repaint',
            'subMode': 'extend',
            'sourceJobId': self.src['id'],
            'extendSeconds': 20,
            'repaintMode': 'balanced',
            'repaintStrength': 0.5,
        })
        self.assertEqual(spec['repaintStart'], 35.0)
        self.assertEqual(spec['repaintEnd'], 60.0)
        self.assertEqual(spec['targetDuration'], 60.0)
        self.assertEqual(spec['summaryLabel'], '뒷부분 +20초 연장')

        long_id = 'b' * 32
        _create_source_song(self.root, ident=long_id, duration=590.0)
        with self.assertRaises(ValueError):
            engine.validate_edit_spec({'mode': 'repaint', 'subMode': 'extend', 'sourceJobId': long_id, 'extendSeconds': 20})

    def test_cover_and_retake_validation_and_retake_seed_inheritance(self):
        cover_spec, _ = engine.validate_edit_spec({
            'mode': 'cover',
            'sourceJobId': self.src['id'],
            'coverStrength': 0.65,
        })
        self.assertEqual(cover_spec['coverStrength'], 0.65)
        self.assertEqual(cover_spec['targetDuration'], 40.0)
        self.assertIn('65%', cover_spec['summaryLabel'])

        retake_spec, _ = engine.validate_edit_spec({
            'mode': 'retake',
            'sourceJobId': self.src['id'],
            'retakeVariance': 0.3,
        })
        self.assertEqual(retake_spec['sourceSeed'], 123456)
        self.assertEqual(retake_spec['sourceAudioCodes'], '<|audio_code_1|>')
        self.assertEqual(retake_spec['retakeVariance'], 0.3)

    def test_rejects_non_song_and_missing_source(self):
        bgm_id = 'c' * 32
        _write_wav(self.root / 'audio' / f'{bgm_id}.wav', 10.0)
        engine.save({'id': bgm_id, 'status': 'completed', 'createdAt': 1, 'settings': {'mode': 'bgm'}})
        with self.assertRaises(ValueError):
            engine.validate_edit_spec({'mode': 'cover', 'sourceJobId': bgm_id})
        with self.assertRaises(FileNotFoundError):
            engine.validate_edit_spec({'mode': 'cover', 'sourceJobId': 'd' * 32})


class WorkshopEngineExecutionTests(unittest.TestCase):
    def test_workshop_skips_windows_plan_phase_and_validates_extended_duration(self):
        probe = '''import argparse, json, sys, wave
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--phase')
p.add_argument('--request')
p.add_argument('--out')
a, _ = p.parse_known_args()
req = Path(a.request)
job = json.loads(req.read_text(encoding='utf-8'))
(req.with_suffix('.argv')).write_text(json.dumps({'phase': a.phase, 'editSpec': job.get('editSpec')}), encoding='utf-8')
target = float(job['editSpec']['targetDuration'])
with wave.open(a.out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(8000)
    w.writeframes(b'\\x01\\x00' * (int(round(target * 8000)) * 2))
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / 'probe.py'
            script.write_text(probe, encoding='utf-8')
            with patch.object(engine, 'DATA', root), \
                 patch.object(engine, 'ready', return_value=True), \
                 patch.object(engine, 'song_paths', return_value=(root, Path(sys.executable), script)), \
                 patch.object(engine.platform, 'system', return_value='Windows'):
                src = _create_source_song(root, duration=20.0)
                settings = {'policy': 'manual', 'mode': 'song', 'model': 'ace-step', 'backend': 'cpu', 'seconds': 40, 'durationMode': 'manual', 'songQuality': 'quality'}
                job = engine.start(
                    settings,
                    src['prompt'],
                    available=4,
                    lyrics=src['lyrics'],
                    language='ko',
                    title='봄날의 산책 (+20초 연장)',
                    edit_spec={'mode': 'repaint', 'subMode': 'extend', 'sourceJobId': src['id'], 'extendSeconds': 20},
                )
                deadline = time.monotonic() + 10
                while engine.ACTIVE and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertIsNone(engine.ACTIVE)
                self.assertEqual(job['status'], 'completed', job.get('error'))
                self.assertEqual(job['parentJobId'], src['id'])
                self.assertEqual(job['rootJobId'], src['id'])
                recorded = json.loads((root / 'jobs' / f"{job['id']}.argv").read_text(encoding='utf-8'))
                self.assertEqual(recorded['phase'], None)
                self.assertEqual(recorded['editSpec']['targetDuration'], 40.0)
                self.assertEqual(job['lyrics'], src['lyrics'])
                self.assertEqual(job['editSpec']['editedLyrics'], src['lyrics'])

    def test_workshop_preserves_original_lyrics_and_records_accumulated_edit_history(self):
        probe = '''import argparse, wave
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--out')
a, _ = p.parse_known_args()
with wave.open(a.out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(8000)
    w.writeframes(b'\\x01\\x00' * (40 * 8000 * 2))
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / 'probe.py'
            script.write_text(probe, encoding='utf-8')
            with patch.object(engine, 'DATA', root), \
                 patch.object(engine, 'ready', return_value=True), \
                 patch.object(engine, 'song_paths', return_value=(root, Path(sys.executable), script)):
                src = _create_source_song(root, duration=40.0)
                settings = {'policy': 'manual', 'mode': 'song', 'model': 'ace-step', 'backend': 'cpu', 'seconds': 40, 'durationMode': 'manual', 'songQuality': 'light'}
                edited_1 = '[Chorus]\n첫 번째 다듬기 수정 가사'
                job1 = engine.start(
                    settings,
                    src['prompt'],
                    available=8,
                    lyrics=edited_1,
                    language='ko',
                    title='봄날의 산책 (구간 수정)',
                    edit_spec={'mode': 'repaint', 'subMode': 'section', 'sourceJobId': src['id'], 'repaintStart': 10.0, 'repaintEnd': 25.0},
                )
                deadline = time.monotonic() + 10
                while engine.ACTIVE and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertEqual(job1['status'], 'completed', job1.get('error'))
                self.assertEqual(job1['lyrics'], src['lyrics'])
                self.assertEqual(job1['editSpec']['originalLyrics'], src['lyrics'])
                self.assertEqual(job1['editSpec']['editedLyrics'], edited_1)
                self.assertEqual(job1['editSpec']['startClock'], '00:10')
                self.assertEqual(job1['editSpec']['endClock'], '00:25')
                self.assertEqual(len(job1['editHistory']), 1)
                self.assertEqual(job1['editHistory'][0]['editedLyrics'], edited_1)
                self.assertEqual(job1['editHistory'][0]['startClock'], '00:10')
                self.assertEqual(job1['editHistory'][0]['endClock'], '00:25')

                edited_2 = '[Outro]\n두 번째 이어 다듬기 가사'
                job2 = engine.start(
                    settings,
                    src['prompt'],
                    available=8,
                    lyrics=edited_2,
                    language='ko',
                    title='봄날의 산책 (구간 수정 2)',
                    edit_spec={'mode': 'repaint', 'subMode': 'section', 'sourceJobId': job1['id'], 'repaintStart': 28.0, 'repaintEnd': 38.0},
                )
                deadline = time.monotonic() + 10
                while engine.ACTIVE and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertEqual(job2['status'], 'completed', job2.get('error'))
                self.assertEqual(job2['lyrics'], src['lyrics'])
                self.assertEqual(len(job2['editHistory']), 2)
                self.assertEqual(job2['editHistory'][0]['editedLyrics'], edited_1)
                self.assertEqual(job2['editHistory'][1]['editedLyrics'], edited_2)
                self.assertEqual(job2['editHistory'][1]['startClock'], '00:28')
                self.assertEqual(job2['editHistory'][1]['endClock'], '00:38')


class WorkshopRunnerInvocationTests(unittest.TestCase):
    def test_song_runner_edit_spec_skips_llm_and_passes_expected_params(self):
        repo_root = Path(__file__).resolve().parent.parent
        for mode_case in ('repaint', 'cover', 'retake'):
            with self.subTest(mode=mode_case), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                engine_dir = tmp_path / 'engines' / 'ace-step'
                (engine_dir / 'checkpoints' / 'Qwen3-Embedding-0.6B').mkdir(parents=True, exist_ok=True)
                mock_pkg = tmp_path / 'mock_libs'
                (mock_pkg / 'acestep' / 'core' / 'generation' / 'handler').mkdir(parents=True, exist_ok=True)
                (mock_pkg / 'transformers').mkdir(parents=True, exist_ok=True)
                (mock_pkg / 'torch').mkdir(parents=True, exist_ok=True)
                (mock_pkg / 'numpy.py').write_text('''import math
float32 = float
class random:
    @staticmethod
    def seed(s): pass
class _FakeArr:
    def __init__(self, data=None, ndim=2):
        self._vals = list(data) if data is not None else [0.1, 0.1, 0.1, 0.1]
        self.ndim = ndim
        self.size = len(self._vals)
    @property
    def T(self): return self
    def all(self): return all(bool(v) for v in self._vals)
    def __iter__(self): return iter(self._vals)
    def __mul__(self, other): return _FakeArr([v * other for v in self._vals], self.ndim)
def ones(shape, dtype=None): return _FakeArr([0.1, 0.1, 0.1, 0.1], 2)
def asarray(x, dtype=None): return x if isinstance(x, _FakeArr) else _FakeArr([0.1, 0.1], 2)
def isfinite(x): return _FakeArr([math.isfinite(v) for v in (x._vals if isinstance(x, _FakeArr) else [x])], 1)
def any(x): return builtins_any(x._vals) if isinstance(x, _FakeArr) else bool(x)
builtins_any = __builtins__['any'] if isinstance(__builtins__, dict) else __builtins__.any
def abs(x): return _FakeArr([__builtins__['abs'](v) if isinstance(__builtins__, dict) else getattr(__builtins__, 'abs')(v) for v in x._vals], x.ndim)
def max(x): return __builtins__['max'](x._vals) if isinstance(__builtins__, dict) else getattr(__builtins__, 'max')(x._vals)
''', encoding='utf-8')
                (mock_pkg / 'soundfile.py').write_text('''import wave
def write(path, data, rate, subtype=None):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(int(rate))
        w.writeframes(b'\\x01\\x00' * 16)
''', encoding='utf-8')
                (mock_pkg / 'mlx' / '__init__.py').mkdir(parents=True, exist_ok=True)

                (mock_pkg / 'torch' / '__init__.py').write_text('''class _Cuda:
    @staticmethod
    def is_available(): return False
    @staticmethod
    def manual_seed(*a): pass
    @staticmethod
    def manual_seed_all(*a): pass
    @staticmethod
    def empty_cache(): pass
class _Version:
    cuda = None
cuda = _Cuda()
version = _Version()
__version__ = "2.0.0"
def manual_seed(*a): pass
''', encoding='utf-8')

                (mock_pkg / 'transformers' / '__init__.py').write_text('''class AutoTokenizer:
    @classmethod
    def from_pretrained(cls, *a, **k): return cls()
    def __call__(self, text, **k): return {'input_ids': [1, 2, 3]}
''', encoding='utf-8')

                (mock_pkg / 'acestep' / '__init__.py').write_text('', encoding='utf-8')
                (mock_pkg / 'acestep' / 'constants.py').write_text('''TASK_INSTRUCTIONS = {
    'text2music': 'Fill:',
    'repaint': 'Repaint:',
    'cover': 'Cover:',
}
''', encoding='utf-8')
                (mock_pkg / 'acestep' / 'llm_inference.py').write_text('''class LLMHandler:
    def __init__(self):
        raise AssertionError('LLMHandler must NOT be called during workshop edit!')
''', encoding='utf-8')
                (mock_pkg / 'acestep' / 'core' / '__init__.py').write_text('', encoding='utf-8')
                (mock_pkg / 'acestep' / 'core' / 'generation' / '__init__.py').write_text('', encoding='utf-8')
                (mock_pkg / 'acestep' / 'core' / 'generation' / 'handler' / '__init__.py').write_text('', encoding='utf-8')
                (mock_pkg / 'acestep' / 'core' / 'generation' / 'handler' / 'prompt_utils.py').write_text('''class PromptMixin:
    def extract_caption_from_sft_format(self, c): return c
    def build_dit_inputs(self, *a): return 'caption', 'lyrics'
''', encoding='utf-8')
                (mock_pkg / 'acestep' / 'core' / 'generation' / 'handler' / 'metadata_utils.py').write_text('''class MetadataMixin:
    def _build_metadata_dict(self, *a): return {}
''', encoding='utf-8')
                (mock_pkg / 'acestep' / 'handler.py').write_text('''class AceStepHandler:
    def __init__(self, *a, **k):
        self.device = 'cpu'
        self.text_tokenizer = None
    def initialize_service(self, **k): return 'ok', True
''', encoding='utf-8')
                capture_file = tmp_path / 'captured.json'
                (mock_pkg / 'acestep' / 'inference.py').write_text(f'''import json, numpy as np
from dataclasses import dataclass, asdict
@dataclass
class GenerationParams:
    caption: str = ''
    lyrics: str = ''
    instrumental: bool = False
    vocal_language: str = 'ko'
    duration: float = 30.0
    seed: int = 0
    reference_audio: object = None
    audio_codes: str = ''
    bpm: object = None
    keyscale: str = ''
    timesignature: str = ''
    lm_negative_prompt: str = ''
    inference_steps: int = 8
    shift: float = 3.0
    infer_method: str = 'ode'
    sampler_mode: str = 'euler'
    dcw_enabled: bool = True
    thinking: bool = False
    use_cot_metas: bool = False
    use_cot_caption: bool = False
    use_cot_language: bool = False
    enable_normalization: bool = False
    task_type: str = 'text2music'
    instruction: str = ''
    chunk_mask_mode: str = 'auto'
    src_audio: object = None
    repainting_start: float = 0.0
    repainting_end: float = -1
    repaint_mode: str = 'balanced'
    repaint_strength: float = 0.5
    audio_cover_strength: float = 1.0
    cover_noise_strength: float = 0.0
    retake_seed: object = None
    retake_variance: float = 0.0
@dataclass
class GenerationConfig:
    batch_size: int = 1
    use_random_seed: bool = False
    seeds: object = None
    audio_format: str = 'wav'
class _FakeTensor:
    def detach(self): return self
    def float(self): return self
    def cpu(self): return self
    def numpy(self): return np.ones((2, 8000), dtype=np.float32) * 0.1
class _Result:
    success = True
    error = None
    status_message = 'ok'
    audios = [{{'tensor': _FakeTensor(), 'sample_rate': 8000}}]
def generate_music(handler, llm, params, config, save_dir=None):
    with open({repr(str(capture_file))}, 'w', encoding='utf-8') as f:
        json.dump({{'params': asdict(params), 'config': asdict(config)}}, f)
    return _Result()
''', encoding='utf-8')

                data_dir = tmp_path / 'data'
                src_wav = data_dir / 'audio' / ('a' * 32 + '.wav')
                _write_wav(src_wav, 30.0)
                edit_spec = {
                    'mode': mode_case,
                    'sourceJobId': 'a' * 32,
                    'sourceAudioPath': str(src_wav),
                    'sourceDuration': 30.0,
                    'targetDuration': 30.0,
                    'sourceMetadata': {'bpm': 100, 'keyscale': 'C major', 'timesignature': '4', 'language': 'ko'},
                }
                if mode_case == 'repaint':
                    edit_spec.update({'subMode': 'section', 'repaintStart': 5.0, 'repaintEnd': 15.0, 'repaintMode': 'balanced', 'repaintStrength': 0.5, 'editedLyrics': '[Chorus]\n수정 구간 전용 가사'})
                elif mode_case == 'cover':
                    edit_spec.update({'coverStrength': 0.65, 'coverNoiseStrength': 0.0})
                else:
                    edit_spec.update({'retakeVariance': 0.3, 'sourceSeed': 777, 'sourceAudioCodes': '<|audio_code_10|>'})

                req_path = tmp_path / 'req.json'
                req_path.write_text(json.dumps({
                    'id': 'b' * 32,
                    'prompt': 'warm piano ballad',
                    'lyrics': '[Verse]\n원본 전체 가사',
                    'language': 'ko',
                    'seed': 999,
                    'settings': {'mode': 'song', 'model': 'ace-step', 'backend': 'cpu', 'peakDb': -8},
                    'editSpec': edit_spec,
                }), encoding='utf-8')

                env = {
                    **os.environ,
                    'LOCAL_MUSIC_DATA': str(data_dir),
                    'LOCAL_MUSIC_ENGINES': str(tmp_path / 'engines'),
                    'PYTHONPATH': str(mock_pkg) + os.pathsep + str(repo_root),
                }
                out_wav = tmp_path / 'out.wav'
                prog_json = tmp_path / 'out.progress.json'
                proc = subprocess.run(
                    [sys.executable, str(repo_root / 'runners' / 'song.py'), '--request', str(req_path), '--out', str(out_wav), '--progress', str(prog_json)],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                captured = json.loads(capture_file.read_text(encoding='utf-8'))
                params = captured['params']
                config = captured['config']
                if mode_case == 'repaint':
                    self.assertEqual(params['task_type'], 'repaint')
                    self.assertEqual(params['chunk_mask_mode'], 'explicit')
                    self.assertEqual(params['repainting_start'], 5.0)
                    self.assertEqual(params['repainting_end'], 15.0)
                    self.assertEqual(params['src_audio'], str(src_wav))
                    self.assertEqual(params['lyrics'], '[Chorus]\n수정 구간 전용 가사')
                elif mode_case == 'cover':
                    self.assertEqual(params['task_type'], 'cover')
                    self.assertEqual(params['audio_cover_strength'], 0.65)
                    self.assertEqual(params['src_audio'], str(src_wav))
                else:
                    self.assertEqual(params['task_type'], 'text2music')
                    self.assertEqual(params['audio_codes'], '<|audio_code_10|>')
                    self.assertEqual(params['seed'], 777)
                    self.assertEqual(config['seeds'], [777])
                    self.assertEqual(params['retake_seed'], 999)
                    self.assertEqual(params['retake_variance'], 0.3)


class WorkshopHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch_app = patch.object(app, 'DATA', Path(self.tmp.name))
        self.patch_eng = patch.object(engine, 'DATA', Path(self.tmp.name))
        self.patch_app.start()
        self.patch_eng.start()
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.patch_app.stop()
        self.patch_eng.stop()
        self.tmp.cleanup()

    def test_workshop_script_served_and_edit_spec_forwarded(self):
        with urllib.request.urlopen(self.base + '/song-workshop.js') as r:
            self.assertEqual(r.status, 200)
            self.assertIn('javascript', r.headers['Content-Type'])
            self.assertIn('SongWorkshop', r.read().decode('utf-8'))

        payload = {
            'settings': {'policy': 'manual', 'mode': 'song', 'model': 'ace-step', 'backend': 'cpu', 'seconds': 30, 'durationMode': 'manual'},
            'prompt': 'warm piano',
            'lyrics': '[Verse]\n가사',
            'language': 'ko',
            'editSpec': {'mode': 'cover', 'sourceJobId': 'f' * 32, 'coverStrength': 0.85},
        }
        req = urllib.request.Request(self.base + '/api/generate', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req)
        self.assertEqual(err.exception.code, 404)
        err.exception.close()

        with patch.object(engine, 'start', return_value={'id': '1' * 32, 'settings': payload['settings']}) as mocked_start:
            req2 = urllib.request.Request(self.base + '/api/generate', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req2) as resp:
                self.assertEqual(resp.status, 202)
            mocked_start.assert_called_once()
            self.assertEqual(mocked_start.call_args.kwargs['edit_spec'], payload['editSpec'])
