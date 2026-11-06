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


def bootstrap_python():
    """Use an ordinary bundled Windows interpreter, never a uv minor-version junction."""
    explicit=os.environ.get('LOCAL_MUSIC_BOOTSTRAP_PYTHON')
    candidate=Path(explicit) if explicit else ROOT/'runtime-python'/'python.exe'
    if candidate.is_file():return str(candidate)
    if sys.platform=='win32' and getattr(sys,'frozen',False):
        raise RuntimeError('앱에 포함된 Python 실행 환경을 찾지 못했습니다. 최신 설치 파일로 다시 설치해 주세요.')
    return None


def create_venv(folder):
    import subprocess
    folder=Path(folder)
    python=bootstrap_python()
    if python:
        # Re-running this refreshes redirects after upgrades, preserving site-packages.
        subprocess.run([python,'-m','venv','--without-pip','--copies',str(folder)],check=True,**background_options())
    else:
        executable=folder/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        if not executable.exists():subprocess.run([uv_path(),'venv','--python','3.11',str(folder)],check=True,**background_options())


def background_options(group=False):
    """Run console tools without a Windows console, keeping process cancellation available."""
    import subprocess
    if sys.platform=='win32':
        return {'creationflags':subprocess.CREATE_NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if group else 0)}
    return {'start_new_session':True} if group else {}
