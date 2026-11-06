"""Lightweight translation metadata and text segmentation (no ML imports)."""
import platform
import json
import re
from pathlib import Path

from app_paths import ROOT, ENGINE_ROOT
FOLDER=ENGINE_ROOT/'translation'
MODEL_ID='Helsinki-NLP/opus-mt-ko-en'
REVISION=(ROOT/'translation-model-version.txt').read_text(encoding='utf-8').strip()
HANGUL=re.compile(r'[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]')

def has_korean(text):
    return bool(HANGUL.search(text))

def runtime_paths():
    return FOLDER/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python'),FOLDER/'model'

def ready():
    python,model=runtime_paths()
    if not python.is_file() or not all((model/name).is_file() for name in ('model.bin','config.json','shared_vocabulary.json','source.spm','target.spm','source.json')):
        return False
    try:
        source=json.loads((model/'source.json').read_text(encoding='utf-8'))
        return source.get('model')==MODEL_ID and source.get('revision')==REVISION
    except (OSError, ValueError):
        return False

def translate_segments(text,translate):
    """Preserve English-only lines/sentences, especially appended style presets."""
    parts=re.split(r'(\r?\n+|(?<=[.!?。！？])[^\S\r\n]+)',text)
    result=[]
    for part in parts:
        if not has_korean(part):
            result.append(part);continue
        match=re.fullmatch(r'(\s*)(.*?)(\s*)',part,flags=re.S)
        prefix,core,suffix=match.groups()
        english=translate(core).strip()
        if not english or has_korean(english):
            raise ValueError('영어 설명으로 변환하지 못했습니다. 설명을 간단히 쓰거나 영어로 입력해 주세요.')
        result.append(prefix+english+suffix)
    return ''.join(result)

def token_chunks(tokens,limit=192):
    """Split without dropping tokens; leave room for English expansion."""
    chunks=[]
    while tokens:
        end=min(limit,len(tokens))
        if end<len(tokens):
            for cut in range(end,max(0,limit//2),-1):
                if tokens[cut].startswith('▁'):end=cut;break
        chunks.append(tokens[:end]+['</s>']);tokens=tokens[end:]
    return chunks
