"""Preserve sung text while separating explicitly instrumental sections."""
import re

TAG=re.compile(r'^\s*\[([^\]]+)\]\s*(.*)$')
ALIASES={'인트로':'Intro','전주':'Intro','아웃트로':'Outro','아웃로':'Outro','후주':'Outro','간주':'Instrumental','벌스':'Verse','후렴':'Chorus','브릿지':'Bridge'}


def prepare(text, instrumental_edges=True):
    lines=[];directions=[];section=None
    for line in text.splitlines():
        match=TAG.match(line)
        if match:
            raw,following=match.groups();name=ALIASES.get(raw.strip(),raw.strip())
            section=name.lower()
            lines.append('['+name+']')
            line=following
        if instrumental_edges and section in ('intro','outro','instrumental'):
            if line.strip():directions.append({'section':section,'text':line.strip().strip('()（）')})
        else:lines.append(line)
    lyrics='\n'.join(lines).strip()
    # Section tags alone are not vocal lyrics.
    sung='\n'.join(line for line in lines if line.strip() and not TAG.match(line))
    if not sung.strip():raise ValueError('부를 가사가 없습니다. [Verse]나 [Chorus] 아래에 가사를 입력하거나 Intro·Outro 연주 처리를 꺼 주세요.')
    return {'lyrics':lyrics,'directions':directions}


def check_lyric_tokens(tokenizer, lyrics, language):
    formatted=f'# Languages\n{language}\n\n# Lyric\n{lyrics}<|endoftext|>'
    count=len(tokenizer(formatted,truncation=False)['input_ids'])
    if count>2048:raise ValueError(f'가사가 엔진 한도(2,048토큰)를 초과했습니다: {count:,}토큰. 뒷부분이 누락되지 않도록 가사를 나누거나 줄여 주세요.')
    return count


def check_audio_codes(codes, duration):
    count=len(re.findall(r'<\|audio_code_\d+\|>',codes or ''))
    if count<duration*5-5:
        raise ValueError(f'곡 구성이 끝까지 생성되지 않았습니다 ({count/5:.1f}초 / 계획 {duration}초). 가사를 나누거나 더 짧게 작성해 다시 시도해 주세요.')
    return count
