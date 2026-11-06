"""Separate immutable app resources from writable per-user engines and data."""
import os
import shutil
import sys
from pathlib import Path

ROOT=Path(os.environ.get('LOCAL_MUSIC_RESOURCES',Path(__file__).resolve().parent))
DATA=Path(os.environ.get('LOCAL_MUSIC_DATA',Path.home()/'.local-music-studio'))
def installed_storage(executable=None, system=None):
    executable=Path(executable or sys.executable).resolve()
    if (system or sys.platform)=='darwin':
        bundle=next((parent for parent in executable.parents if parent.suffix=='.app'),None)
        if bundle:return bundle.parent/'SoriSoop Data'
    return executable.parent/'SoriSoop Data'

STORAGE=Path(os.environ.get('LOCAL_MUSIC_STORAGE',installed_storage() if getattr(sys,'frozen',False) else DATA))
ENGINE_ROOT=Path(os.environ.get('LOCAL_MUSIC_ENGINES',STORAGE/'engines' if getattr(sys,'frozen',False) else ROOT/'engines'))

def uv_path():
    bundled=ROOT/'tools'/('uv.exe' if sys.platform=='win32' else 'uv')
    executable=os.environ.get('LOCAL_MUSIC_UV') or (str(bundled) if bundled.is_file() else shutil.which('uv'))
    if not executable:raise RuntimeError('설치 도구를 찾을 수 없습니다. 앱을 다시 설치하거나 uv를 설치해 주세요.')
    return executable
