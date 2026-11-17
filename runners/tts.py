"""Isolated subprocess runner for Qwen3-TTS CustomVoice generation."""
import argparse
import json
import sys
from pathlib import Path


def pick_device():
    import torch
    if torch.cuda.is_available():
        return 'cuda:0', torch.bfloat16
    if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available():
        return 'mps', torch.float32
    return 'cpu', torch.float32


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--model-dir', default='')
    args = parser.parse_args()

    req = json.loads(Path(args.request).read_text(encoding='utf-8'))
    voice_mode = req.get('voiceMode') or 'custom'
    text = (req.get('text') or '').strip()
    speaker = req.get('speaker') or 'Sohee'
    language = req.get('language') or 'Korean'
    instruct = (req.get('instruct') or '').strip()
    if not text:
        print('생성할 텍스트가 비어 있습니다.', file=sys.stderr)
        sys.exit(1)
    if voice_mode == 'design' and not instruct:
        print('새 음색 디자인에는 목소리 스타일 설명이 필요합니다.', file=sys.stderr)
        sys.exit(1)

    import numpy as np
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel

    device_map, dtype = pick_device()
    default_repo = 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign' if voice_mode == 'design' else 'Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice'
    model_source = args.model_dir if (args.model_dir and Path(args.model_dir).exists()) else default_repo
    print(f'Loading Qwen3-TTS ({model_source}) on {device_map}...', flush=True)
    model = Qwen3TTSModel.from_pretrained(
        model_source,
        device_map=device_map,
        dtype=dtype,
    )
    if voice_mode == 'design':
        print(f'Designing voice with language={language}...', flush=True)
        wavs, sr = model.generate_voice_design(text=text, language=language, instruct=instruct)
    else:
        kwargs = {'text': text, 'language': language, 'speaker': speaker}
        if instruct:
            kwargs['instruct'] = instruct
        print(f'Generating speech with speaker={speaker}, language={language}...', flush=True)
        wavs, sr = model.generate_custom_voice(**kwargs)
    audio = np.asarray(wavs[0], dtype=np.float32)
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, sr, subtype='PCM_16')
    print(f'Saved {out_path} ({sr} Hz)', flush=True)


if __name__ == '__main__':
    main()
