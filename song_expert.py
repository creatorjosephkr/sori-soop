"""ACE-Step 1.5 expert quality controls shared by the server and song runner."""

DEFAULTS = {
    'inferenceSteps': 8,
    'shift': 3.0,
    'inferMethod': 'ode',
    'sampler': 'euler',
    'dcw': True,
    'lmTemperature': 0.85,
    'lmCfgScale': 2.0,
    'lmTopP': 0.9,
}

RANGES = {
    'inferenceSteps': (4, 20),
    'shift': (1.0, 5.0),
    'lmTemperature': (0.3, 1.5),
    'lmCfgScale': (1.0, 4.0),
    'lmTopP': (0.5, 1.0),
}

CHOICES = {'inferMethod': ('ode', 'sde'), 'sampler': ('euler', 'heun')}

LABELS = {
    'inferenceSteps': '확산 단계 수', 'shift': '타임스텝 시프트', 'inferMethod': '확산 방식',
    'sampler': '샘플러', 'dcw': '웨이블릿 보정(DCW)', 'lmTemperature': '구성 다양성',
    'lmCfgScale': '설명 반영 강도', 'lmTopP': '후보 범위(Top-p)',
}


def normalize(value):
    """Return a complete, validated expert settings dict; missing keys use defaults."""
    if value is None:
        return dict(DEFAULTS)
    if not isinstance(value, dict):
        raise ValueError('전문가 설정 형식을 확인하세요.')
    unknown = set(value) - set(DEFAULTS)
    if unknown:
        raise ValueError('알 수 없는 전문가 설정 항목이 있습니다.')
    result = dict(DEFAULTS)
    for key, raw in value.items():
        label = LABELS[key]
        if key == 'dcw':
            if type(raw) is not bool:
                raise ValueError(f'{label} 값을 확인하세요.')
            result[key] = raw
        elif key in CHOICES:
            if raw not in CHOICES[key]:
                raise ValueError(f'{label} 값을 확인하세요.')
            result[key] = raw
        else:
            low, high = RANGES[key]
            if type(raw) not in (int, float) or raw != raw:
                raise ValueError(f'{label} 값을 확인하세요.')
            if key == 'inferenceSteps':
                if int(raw) != raw:
                    raise ValueError(f'{label}는 정수로 입력하세요.')
                raw = int(raw)
            if not low <= raw <= high:
                raise ValueError(f'{label}는 {low}~{high} 범위로 설정하세요.')
            result[key] = raw if key == 'inferenceSteps' else round(float(raw), 2)
    return result


def is_default(value):
    return normalize(value) == DEFAULTS
