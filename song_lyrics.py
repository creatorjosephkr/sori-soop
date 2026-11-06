"""Validate full lyric and caption inputs without truncation or rearrangement."""
import re

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


def check_caption_tokens(tokenizer, text, *, formatted=True):
    """Count untruncated, real encoder tokens, including the caller's template."""
    count=len(tokenizer(text,truncation=False)['input_ids'])
    if count>256:
        scope='번역된 음악 설명·내부 지시문 합계' if formatted else '번역된 음악 설명 자체'
        raise ValueError(f'노래 설명이 엔진 한도(256토큰)를 초과했습니다: {scope} {count:,}토큰, 최소 {count-256:,}토큰 초과. 음악 설명을 줄여 다시 시도해 주세요. 설명은 자동으로 잘리지 않았습니다.')
    return count
