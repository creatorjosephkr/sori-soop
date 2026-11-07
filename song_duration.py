"""Duration policy shared by request validation and the song adapter."""
import math
import re

MIN_SECONDS=10
MAX_SECONDS=600


def automatic(settings):return settings.get('mode')=='song' and settings.get('durationMode','manual')=='auto'


def explicit_bpm(caption):
    caption=re.sub(r'\b\d+(?:\.\d+)?\s*[-~–—]\s*\d+(?:\.\d+)?\s*bpm\b','',caption or '',flags=re.I)
    number=r'(\d{1,4})(?![\d.]|\s*[-~–—]\s*\d)'
    patterns=(r'(?<![\w.\-–—~])'+number+r'\s*bpm\b',r'\bbpm\s*[:=]?\s*'+number)
    found={int(match.group(1)) for pattern in patterns for match in re.finditer(pattern,caption or '',flags=re.I)}
    if len(found)>1:raise ValueError('음악 설명에 서로 다른 BPM이 여러 개 있습니다. 곡 전체에 적용할 BPM 하나만 적어 주세요.')
    if not found:return None
    bpm=found.pop()
    if not 30<=bpm<=300:raise ValueError('노래 템포는 30~300 BPM 범위로 적어 주세요.')
    return bpm


def plan_options(settings,caption='',language=None):
    metadata={} if automatic(settings) else {'duration':settings['seconds']}
    bpm=explicit_bpm(caption)
    if bpm is not None:metadata['bpm']=bpm
    if language and language!='unknown':metadata['language']=language
    return {'target_duration':None if automatic(settings) else settings['seconds'],'user_metadata':metadata or None}


def check_planned_bpm(requested,metadata):
    if requested is None:return
    try:actual=float(metadata.get('bpm'))
    except (TypeError,ValueError):actual=None
    if actual!=requested:
        raise ValueError(f'요청한 {requested} BPM과 곡 구성의 템포({metadata.get("bpm", "확인 불가")} BPM)가 일치하지 않습니다. 다른 템포로 생성하지 않고 중단했습니다. 다시 시도해 주세요.')


def check_planned_language(requested,metadata):
    if not requested or requested=='unknown':return
    if str(metadata.get('language','')).lower()!=requested:
        raise ValueError(f'요청한 보컬 언어({requested})와 곡 구성 언어({metadata.get("language", "확인 불가")})가 일치하지 않습니다. 다른 언어로 생성하지 않고 중단했습니다. 다시 시도해 주세요.')


def planned_seconds(settings,metadata,audio_codes):
    if not automatic(settings):return settings['seconds']
    value=metadata.get('duration')
    if isinstance(value,bool):value=None
    try:duration=float(value)
    except (TypeError,ValueError):duration=0
    if not math.isfinite(duration) or duration<=0:
        duration=len(re.findall(r'<\|audio_code_\d+\|>',audio_codes or ''))/5
    if not MIN_SECONDS<=duration<=MAX_SECONDS:
        raise ValueError('가사에서 정한 노래 길이가 지원 범위(10~600초)를 벗어났습니다. 가사를 줄이거나 수동 길이를 선택해 주세요.')
    return math.ceil(duration)
