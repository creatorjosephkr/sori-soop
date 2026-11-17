"""Qwen3-TTS CustomVoice setup, generation, and reference-audio registration."""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from app_paths import ENGINE_ROOT, ROOT, background_options, create_venv, uv_path
from audio_export import write_mp3
from audio_processing import apply_wav_metadata
import engine

MODEL_REPO = 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice'
VOICE_DESIGN_REPO = 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign'

SPEAKERS = [
    {'id': 'Sohee', 'label': '소희 (Sohee) · 한국어 여성 · 따뜻하고 감성적'},
    {'id': 'Serena', 'label': '세레나 (Serena) · 여성 · 부드럽고 선명함'},
    {'id': 'Vivian', 'label': '비비안 (Vivian) · 여성 · 밝고 경쾌함'},
    {'id': 'Ono_Anna', 'label': '안나 (Ono Anna) · 여성 · 청아하고 경쾌함'},
    {'id': 'Ryan', 'label': '라이언 (Ryan) · 남성 · 리드미컬하고 자연스러움'},
    {'id': 'Aiden', 'label': '에이든 (Aiden) · 남성 · 맑고 부드러움'},
    {'id': 'Dylan', 'label': '딜런 (Dylan) · 남성 · 차분하고 담백함'},
    {'id': 'Eric', 'label': '에릭 (Eric) · 남성 · 안정적인 중저음'},
    {'id': 'Uncle_Fu', 'label': '푸 삼촌 (Uncle Fu) · 남성 · 깊고 따뜻한 저음'},
]

LANGUAGES = [
    {'id': 'Korean', 'label': '한국어'},
    {'id': 'English', 'label': '영어 (English)'},
    {'id': 'Japanese', 'label': '일본어 (日本語)'},
    {'id': 'Chinese', 'label': '중국어 (中文)'},
    {'id': 'Auto', 'label': '자동 감지'},
]

_LOCK = threading.Lock()
_SETUP_STATE = {'installing': False, 'installingMode': '', 'message': '', 'error': '', 'logs': [], 'startedAt': 0.0}


def tts_root():
    return ENGINE_ROOT / 'qwen-tts'


def tts_python():
    folder = tts_root() / '.venv'
    return folder / ('Scripts/python.exe' if platform.system() == 'Windows' else 'bin/python')


def tts_model_dir(voice_mode='custom'):
    return tts_root() / ('model-voice-design' if voice_mode == 'design' else 'model')


def preview_dir():
    return engine.DATA / 'tts-previews'


def runtime_ready():
    py = tts_python()
    if not py.exists():
        return False
    marker = tts_root() / '.runtime-ready'
    return marker.is_file()


def model_ready(voice_mode='custom'):
    mdir = tts_model_dir(voice_mode)
    return (mdir / 'config.json').is_file() and (mdir / '.model-ready').is_file()


def is_ready(voice_mode='custom'):
    return runtime_ready() and model_ready(voice_mode)


def status():
    with _LOCK:
        setup_copy = {
            'installing': _SETUP_STATE['installing'],
            'installingMode': _SETUP_STATE.get('installingMode', ''),
            'message': _SETUP_STATE['message'],
            'error': _SETUP_STATE['error'],
            'logs': list(_SETUP_STATE['logs']),
            'elapsedSeconds': int(max(0, time.time() - _SETUP_STATE['startedAt'])) if (_SETUP_STATE['installing'] and _SETUP_STATE['startedAt']) else 0,
        }
    return {
        'ready': is_ready('custom'),
        'designReady': is_ready('design'),
        'runtimeReady': runtime_ready(),
        'modelReady': model_ready('custom'),
        'designModelReady': model_ready('design'),
        'installing': setup_copy['installing'],
        'installingMode': setup_copy['installingMode'],
        'message': setup_copy['message'],
        'error': setup_copy['error'],
        'logs': setup_copy['logs'],
        'elapsedSeconds': setup_copy['elapsedSeconds'],
        'speakers': SPEAKERS,
        'languages': LANGUAGES,
    }


def _append_log(line):
    text = (line or '').strip()
    if not text:
        return
    with _LOCK:
        logs = _SETUP_STATE['logs']
        logs.append(text)
        if len(logs) > 40:
            del logs[:-40]


def _set_setup(installing=None, message=None, error=None):
    with _LOCK:
        if installing is not None:
            _SETUP_STATE['installing'] = installing
        if message is not None:
            _SETUP_STATE['message'] = message
        if error is not None:
            _SETUP_STATE['error'] = error


def _run_logged(cmd):
    env = dict(os.environ)
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONUTF8'] = '1'
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        **background_options(),
    )
    buf = []
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            if buf:
                _append_log(''.join(buf))
            break
        if ch in ('\n', '\r'):
            if buf:
                _append_log(''.join(buf))
                buf.clear()
        else:
            buf.append(ch)
    code = proc.wait()
    if code != 0:
        raise subprocess.CalledProcessError(code, cmd)


def _run_setup_worker(voice_mode='custom'):
    try:
        root = tts_root()
        root.mkdir(parents=True, exist_ok=True)
        py = tts_python()
        if not py.exists():
            _set_setup(message='1/3 · 음성 생성 전용 Python 환경을 만들고 있습니다…')
            _append_log('Python 가상환경(.venv)을 생성하고 있습니다...')
            if (root / '.venv').exists():
                shutil.rmtree(root / '.venv', ignore_errors=True)
            create_venv(root / '.venv')

        if not runtime_ready():
            _set_setup(message='2/3 · Qwen3-TTS 및 PyTorch 패키지를 설치하고 있습니다…')
            _append_log('uv로 torch, qwen-tts, soundfile, huggingface_hub 설치를 시작합니다...')
            uv = uv_path()
            if platform.system() == 'Windows':
                try:
                    from song_runtime import detect_nvidia_gpu
                    gpu = detect_nvidia_gpu()
                except Exception:
                    gpu = None
                if gpu is not None and gpu.get('vramGB', 0) >= 4.0:
                    _append_log(f"NVIDIA GPU 감지 ({gpu.get('name')}): CUDA 가속 PyTorch를 설치합니다...")
                    _run_logged([uv, 'pip', 'install', '--python', str(py), 'torch', 'torchvision', 'torchaudio', '--index-url', 'https://download.pytorch.org/whl/cu128'])
            _run_logged([uv, 'pip', 'install', '--python', str(py), 'torch', 'qwen-tts', 'soundfile', 'huggingface_hub'])
            (root / '.runtime-ready').write_text('ok\n', encoding='utf-8')
            _append_log('패키지 설치를 완료했습니다.')

        repo = VOICE_DESIGN_REPO if voice_mode == 'design' else MODEL_REPO
        label = '1.7B 새 음색 디자인 모델(약 3.5GB)' if voice_mode == 'design' else '0.6B 기본 성우 모델(약 1.5GB)'
        if not model_ready(voice_mode):
            _set_setup(message=f'3/3 · Qwen3-TTS {label}을 다운로드하고 있습니다…')
            _append_log(f'Hugging Face에서 {repo} 다운로드를 시작합니다...')
            mdir = tts_model_dir(voice_mode)
            mdir.mkdir(parents=True, exist_ok=True)
            dl_code = (
                "from huggingface_hub import snapshot_download; "
                f"snapshot_download({repo!r}, local_dir={str(mdir)!r})"
            )
            _run_logged([str(py), '-u', '-c', dl_code])
            (mdir / '.model-ready').write_text('ok\n', encoding='utf-8')
            _append_log('모델 다운로드를 완료했습니다.')

        _set_setup(installing=False, message='Qwen3-TTS 모델 준비가 완료되었습니다.', error='')
    except Exception as exc:
        _append_log(f'오류: {exc}')
        _set_setup(installing=False, message='', error=f'설치 실패: {exc}')
    finally:
        with _LOCK:
            _SETUP_STATE['installingMode'] = ''


def start_setup(voice_mode='custom'):
    if voice_mode not in ('custom', 'design'):
        voice_mode = 'custom'
    with _LOCK:
        if _SETUP_STATE['installing']:
            return status()
        if is_ready(voice_mode):
            return status()
        _SETUP_STATE['installing'] = True
        _SETUP_STATE['installingMode'] = voice_mode
        _SETUP_STATE['startedAt'] = time.time()
        _SETUP_STATE['logs'] = []
        _SETUP_STATE['message'] = '설치를 시작하고 있습니다…'
        _SETUP_STATE['error'] = ''
    thread = threading.Thread(target=_run_setup_worker, args=(voice_mode,), daemon=True)
    thread.start()
    return status()


def generate(text, speaker='Sohee', language='Korean', instruct='', voice_mode='custom'):
    if voice_mode not in ('custom', 'design'):
        raise ValueError('지원하지 않는 음성 생성 방식입니다.')
    text = (text or '').strip()
    instruct = (instruct or '').strip()
    if not text:
        raise ValueError('음성으로 만들 대사나 가사를 입력하세요.')
    if len(text) > 1000:
        raise ValueError('텍스트는 1,000자 이하로 입력하세요.')
    if voice_mode == 'design':
        if not instruct:
            raise ValueError('새 음색 디자인에는 목소리 스타일 설명을 입력해 주세요.')
    else:
        valid_speakers = {s['id'] for s in SPEAKERS}
        if speaker not in valid_speakers:
            raise ValueError('지원하지 않는 성우입니다.')
    valid_langs = {l['id'] for l in LANGUAGES}
    if language not in valid_langs:
        raise ValueError('지원하지 않는 언어입니다.')
    if not is_ready(voice_mode):
        raise RuntimeError('선택한 Qwen3-TTS 모델이 아직 설치되지 않았습니다. 먼저 모델을 설치해 주세요.')

    ident = uuid.uuid4().hex
    pdir = preview_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    req_path = pdir / f'{ident}.json'
    out_path = pdir / f'{ident}.wav'
    meta_path = pdir / f'{ident}.meta.json'

    req_path.write_text(json.dumps({
        'voiceMode': voice_mode,
        'text': text,
        'speaker': speaker,
        'language': language,
        'instruct': instruct,
    }, ensure_ascii=False), encoding='utf-8')

    runner = ROOT / 'runners' / 'tts.py'
    env = dict(os.environ)
    env['PYTHONUTF8'] = '1'
    try:
        proc = subprocess.run(
            [str(tts_python()), '-u', str(runner), '--request', str(req_path), '--out', str(out_path), '--model-dir', str(tts_model_dir(voice_mode))],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            **background_options(),
        )
    finally:
        req_path.unlink(missing_ok=True)

    if proc.returncode != 0 or not out_path.is_file():
        err = (proc.stderr or proc.stdout or '음성 생성에 실패했습니다.').strip()
        raise RuntimeError(err[-500:])

    voice_title = f'보컬 음색 · {instruct[:24]}' if voice_mode == 'design' else f'보컬 음성 · {speaker}'
    apply_wav_metadata(out_path, title=voice_title)

    filename = f"qwen3_{'design' if voice_mode == 'design' else speaker.lower()}_{ident[:6]}.wav"
    meta = {
        'id': ident,
        'voiceMode': voice_mode,
        'speaker': speaker,
        'language': language,
        'text': text,
        'instruct': instruct,
        'filename': filename,
        'createdAt': time.time(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    return {
        'id': ident,
        'voiceMode': voice_mode,
        'audioUrl': f'/tts-audio/{ident}.wav',
        'downloadUrl': f'/tts-audio/{ident}.wav?download=1',
        'mp3Url': f'/tts-audio/{ident}.mp3?download=1',
        'filename': filename,
        'speaker': speaker,
        'language': language,
        'instruct': instruct,
    }


def resolve_preview_path(ident):
    if not isinstance(ident, str) or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('잘못된 음성 ID입니다.')
    path = preview_dir() / f'{ident}.wav'
    meta_path = preview_dir() / f'{ident}.meta.json'
    if not path.is_file():
        raise FileNotFoundError('생성된 음성을 찾을 수 없습니다.')
    meta = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            meta = {}
    return path, meta


def register_as_reference(ident, custom_name=''):
    path, meta = resolve_preview_path(ident)
    raw = path.read_bytes()
    name = (custom_name or '').strip() or (meta.get('title') or '').strip() or meta.get('filename') or f'qwen3_voice_{ident[:6]}.wav'
    if not name.lower().endswith('.wav'):
        name += '.wav'
    return engine.save_reference_audio(name, raw)


def _preview_title(meta):
    voice_mode = meta.get('voiceMode', 'custom')
    if voice_mode == 'design':
        desc = (meta.get('instruct') or '').strip()
        return '음색 디자인 · ' + (desc[:22] + '…' if len(desc) > 22 else desc)
    speaker_labels = {s['id']: s['label'] for s in SPEAKERS}
    return speaker_labels.get(meta.get('speaker', 'Sohee'), meta.get('speaker', 'Sohee'))


def _build_preview_item(ident, meta):
    voice_mode = meta.get('voiceMode', 'custom')
    custom_title = (meta.get('title') or '').strip()
    return {
        'id': ident,
        'voiceMode': voice_mode,
        'speaker': meta.get('speaker', 'Sohee'),
        'title': custom_title,
        'speakerLabel': custom_title or _preview_title(meta),
        'language': meta.get('language', 'Korean'),
        'text': meta.get('text', ''),
        'instruct': meta.get('instruct', ''),
        'filename': meta.get('filename', f'qwen3_{ident[:6]}.wav'),
        'audioUrl': f'/tts-audio/{ident}.wav',
        'downloadUrl': f'/tts-audio/{ident}.wav?download=1',
        'mp3Url': f'/tts-audio/{ident}.mp3?download=1',
        'createdAt': float(meta.get('createdAt', 0)),
    }


def download_filename(ident, meta, ext):
    raw = (meta.get('title') or '').strip() or Path(meta.get('filename') or f'qwen3_{ident[:6]}.wav').stem
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', '_', raw).strip('. ') or f'qwen3_{ident[:6]}'
    if not safe.startswith('소리숲성우_'):
        safe = f'소리숲성우_{safe}'
    return f'{safe}.{ext}'


def rename_preview(ident, title):
    path, meta = resolve_preview_path(ident)
    clean_title = str(title or '').strip()
    if not 1 <= len(clean_title) <= 100:
        raise ValueError('이름은 1~100자로 입력하세요.')
    meta['title'] = clean_title
    meta_path = preview_dir() / f'{ident}.meta.json'
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    apply_wav_metadata(path, title=clean_title)
    path.with_suffix('.mp3').unlink(missing_ok=True)
    return _build_preview_item(ident, meta)


def list_previews():
    pdir = preview_dir()
    if not pdir.is_dir():
        return []
    items = []
    for meta_path in pdir.glob('*.meta.json'):
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            ident = meta.get('id')
            if not ident or not (pdir / f'{ident}.wav').is_file():
                continue
            items.append(_build_preview_item(ident, meta))
        except Exception:
            continue
    items.sort(key=lambda x: x['createdAt'], reverse=True)
    return items


def export_mp3(ident):
    wav_path, meta = resolve_preview_path(ident)
    mp3_path = wav_path.with_suffix('.mp3')
    if not mp3_path.is_file():
        custom_title = (meta.get('title') or '').strip()
        if custom_title:
            voice_title = custom_title
        else:
            voice_mode = meta.get('voiceMode', 'custom')
            speaker = meta.get('speaker', 'Sohee')
            instruct = (meta.get('instruct') or '').strip()
            voice_title = f'보컬 음색 · {instruct[:24]}' if voice_mode == 'design' else f'보컬 음성 · {speaker}'
        write_mp3(wav_path, mp3_path, title=voice_title)
    return mp3_path, meta


def delete_preview(ident):
    path, _ = resolve_preview_path(ident)
    path.unlink(missing_ok=True)
    path.with_suffix('.mp3').unlink(missing_ok=True)
    (preview_dir() / f'{ident}.meta.json').unlink(missing_ok=True)
