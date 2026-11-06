"""Duration policy shared by request validation and the song adapter."""
import math
import re

MIN_SECONDS=10
MAX_SECONDS=600


def automatic(settings):return settings.get('mode')=='song' and settings.get('durationMode','manual')=='auto'


def plan_options(settings):
    if automatic(settings):return {'target_duration':None,'user_metadata':None}
    return {'target_duration':settings['seconds'],'user_metadata':{'duration':settings['seconds']}}


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
