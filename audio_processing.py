"""Output sample-peak control shared by both local music engines."""
import math
import wave
from array import array
import sys

DEFAULT_PEAK_DB = -8

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

def write_wav(path, audio, rate, peak_db=DEFAULT_PEAK_DB, channels_first=True):
    import soundfile as sf
    limited = limit_peak(audio, peak_db)
    if channels_first and limited.ndim == 2:
        limited = limited.T
    sf.write(str(path), limited, rate, subtype='PCM_16')

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
