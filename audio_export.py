"""Local, streaming PCM16 WAV to MP3 export with ID3 metadata; no external executable needed."""
import os
import sys
import tempfile
import wave
from array import array
from pathlib import Path

APP_NAME = '소리숲 (Sori Soop)'
APP_AUTHOR = '크리에이터 요셉 (CREATOR JOSEPH)'
APP_URL = 'https://blog.naver.com/josephk1010'


def get_app_version():
    try:
        from app_paths import ROOT
        v_file = ROOT / 'VERSION'
        if v_file.is_file():
            return v_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    try:
        v_file = Path(__file__).resolve().parent / 'VERSION'
        if v_file.is_file():
            return v_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    return '1.3.8'


def make_synchsafe(size):
    return bytes([(size >> 21) & 0x7f, (size >> 14) & 0x7f, (size >> 7) & 0x7f, size & 0x7f])


def make_text_frame(frame_id, text):
    data = b'\x01' + text.encode('utf-16')
    return frame_id.encode('ascii') + len(data).to_bytes(4, 'big') + b'\x00\x00' + data


def make_comm_frame(desc, text):
    data = b'\x01kor' + desc.encode('utf-16') + b'\x00\x00' + text.encode('utf-16')
    return b'COMM' + len(data).to_bytes(4, 'big') + b'\x00\x00' + data


def make_url_frame(frame_id, url):
    data = url.encode('latin1')
    return frame_id.encode('ascii') + len(data).to_bytes(4, 'big') + b'\x00\x00' + data


def build_id3v2(title=None, version=None):
    version = version or get_app_version()
    frames = []
    if title:
        frames.append(make_text_frame('TIT2', str(title).strip()))
    frames.append(make_text_frame('TPE1', APP_NAME))
    frames.append(make_text_frame('TSSE', f'{APP_NAME} v{version}'))
    frames.append(make_comm_frame('', f'소리숲 제작: {APP_AUTHOR} | 앱 제공 URL: {APP_URL}'))
    frames.append(make_url_frame('WOAS', APP_URL))
    body = b''.join(frames)
    header = b'ID3\x03\x00\x00' + make_synchsafe(len(body))
    return header + body


def write_mp3(source, target, title=None):
    import lameenc
    source, target = Path(source), Path(target)
    temporary = None
    try:
        with wave.open(str(source), 'rb') as audio:
            if audio.getsampwidth() != 2 or audio.getnchannels() not in (1, 2) or not audio.getnframes():
                raise ValueError('MP3 변환에는 비어 있지 않은 모노 또는 스테레오 PCM16 WAV가 필요합니다.')
            encoder = lameenc.Encoder()
            encoder.set_bit_rate(320)
            encoder.set_in_sample_rate(audio.getframerate())
            encoder.set_channels(audio.getnchannels())
            encoder.set_quality(2)
            encoder.silence()
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.stem+'-', suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                output.write(build_id3v2(title=title))
                while pcm := audio.readframes(65536):
                    if sys.byteorder != 'little':
                        samples = array('h', pcm); samples.byteswap(); pcm = samples.tobytes()
                    output.write(encoder.encode(pcm))
                output.write(encoder.flush())
            if not temporary.stat().st_size:
                raise ValueError('MP3 파일을 생성하지 못했습니다.')
            os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
