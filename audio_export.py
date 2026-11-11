"""Local, streaming PCM16 WAV to MP3 export; no external executable needed."""
import os
import sys
import tempfile
import wave
from array import array
from pathlib import Path


def write_mp3(source, target):
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
