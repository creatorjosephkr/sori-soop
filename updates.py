"""Read public GitHub release metadata; never send local user content."""
import json
import platform
import re
import threading
import time
import urllib.request
from app_paths import ROOT

REPOSITORY = 'https://github.com/creatorjosephkr/sori-soop'
LATEST = 'https://api.github.com/repos/creatorjosephkr/sori-soop/releases/latest'
CURRENT = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
_LOCK = threading.Lock()
_cached = None
_checked_at = 0


def version(value):
    match = re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value or '')
    if not match:
        raise ValueError('정식 버전 정보를 확인할 수 없습니다.')
    return tuple(map(int, match.groups()))


def release_info(release):
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('정식 릴리즈가 아닙니다.')
    tag = release.get('tag_name', '')
    latest = version(tag)
    release_url = REPOSITORY + '/releases/tag/' + tag
    if release.get('html_url') != release_url:
        raise ValueError('올바른 저장소의 릴리즈가 아닙니다.')
    suffix = None
    if platform.system() == 'Darwin' and platform.machine().lower() in ('arm64', 'aarch64'):
        suffix = 'macos-arm64.dmg'
    elif platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64'):
        suffix = 'windows-x64.zip'
    name = f'SoriSoop-{tag.lstrip("v")}-{suffix}' if suffix else None
    download = next((a.get('browser_download_url') for a in release.get('assets', [])
                     if name and a.get('name') == name and a.get('state') == 'uploaded'
                     and a.get('browser_download_url') == REPOSITORY + '/releases/download/' + tag + '/' + name), None)
    return dict(currentVersion=CURRENT, latestVersion=tag.lstrip('v'), available=latest > version(CURRENT),
                releaseUrl=release_url, repositoryUrl=REPOSITORY, downloadUrl=download)


def check():
    global _cached, _checked_at
    with _LOCK:
        if _cached is not None and time.monotonic() - _checked_at < 6 * 3600:
            return dict(_cached)
        request = urllib.request.Request(LATEST, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'SoriSoop/' + CURRENT})
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('릴리즈 정보가 너무 큽니다.')
        result = release_info(json.loads(raw))
        _cached, _checked_at = result, time.monotonic()
        return dict(result)
