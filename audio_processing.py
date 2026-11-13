"""Output sample-peak control and RIFF INFO metadata shared by both local music engines."""
import math
import wave
from array import array
from pathlib import Path
import sys

DEFAULT_PEAK_DB = -8
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


def validate_peak_db(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -24 <= value <= 0:
        raise ValueError('최대 게인은 -24~0dB 범위의 숫자로 설정하세요.')
    return value


def limit_peak(audio, peak_db=DEFAULT_PEAK_DB):
    import numpy as np
    validate_peak_db(peak_db)
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError('오디오에 비어 있거나 유효하지 않은 값이 있습니다.')
    peak = float(np.max(np.abs(audio)))
    # Reserve one PCM16 quantization step so rounding cannot exceed the ceiling.
    ceiling = max(0, 10 ** (peak_db / 20) - 1 / 32768)
    scale = min(1.0, ceiling / peak) if peak else 1.0
    return audio * scale


def write_wav(path, audio, rate, peak_db=DEFAULT_PEAK_DB, channels_first=True, title=None):
    import soundfile as sf
    limited = limit_peak(audio, peak_db)
    if channels_first and limited.ndim == 2:
        limited = limited.T
    sf.write(str(path), limited, rate, subtype='PCM_16')
    apply_wav_metadata(path, title=title)


def apply_wav_metadata(path, title=None, artist=APP_NAME, software=None, comment=f'소리숲 제작: {APP_AUTHOR} | 앱 제공 URL: {APP_URL}'):
    from audio_export import build_id3v2
    path = Path(path)
    if not path.is_file():
        return
    software = software or f'{APP_NAME} v{get_app_version()}'
    raw = path.read_bytes()
    if len(raw) < 12 or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        return
    pos = 12
    chunks = []
    while pos < len(raw):
        if pos + 8 > len(raw):
            break
        cid = raw[pos:pos+4]
        csize = int.from_bytes(raw[pos+4:pos+8], 'little')
        total_size = 8 + csize + (csize % 2)
        cdata = raw[pos:pos+total_size]
        if (cid == b'LIST' and raw[pos+8:pos+12] == b'INFO') or cid in (b'id3 ', b'ID3 '):
            pos += total_size
            continue
        chunks.append(cdata)
        pos += total_size

    # 1) ID3v2 chunk in RIFF (UTF-16 with BOM for macOS Finder / modern DAWs)
    id3_data = build_id3v2(title=title)
    id3_chunk = b'id3 ' + len(id3_data).to_bytes(4, 'little') + id3_data
    if len(id3_data) % 2 == 1:
        id3_chunk += b'\x00'
    chunks.append(id3_chunk)

    # 2) Standard RIFF LIST INFO chunk as fallback
    subchunks = []
    meta = {'INAM': title, 'IART': artist, 'ISFT': software, 'ICMT': comment}
    for key, val in meta.items():
        if not val:
            continue
        encoded = str(val).encode('utf-8') + b'\x00'
        chunk = key.encode('ascii') + len(encoded).to_bytes(4, 'little') + encoded
        if len(encoded) % 2 == 1:
            chunk += b'\x00'
        subchunks.append(chunk)
    body = b'INFO' + b''.join(subchunks)
    info_chunk = b'LIST' + len(body).to_bytes(4, 'little') + body
    chunks.append(info_chunk)

    new_riff_body = b'WAVE' + b''.join(chunks)
    new_raw = b'RIFF' + len(new_riff_body).to_bytes(4, 'little') + new_riff_body
    path.write_bytes(new_raw)


def wav_peak_db(path):
    peak = 0
    with wave.open(str(path), 'rb') as stream:
        if stream.getsampwidth() != 2:
            raise ValueError('최대 피크 검증에는 PCM16 WAV가 필요합니다.')
        while raw := stream.readframes(65536):
            values = array('h', raw)
            if sys.byteorder != 'little':
                values.byteswap()
            peak = max(peak, abs(min(values, default=0)), abs(max(values, default=0)))
    return 20 * math.log10(peak / 32768) if peak else None
