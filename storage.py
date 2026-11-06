"""Place large runtime files beside the installed application, outside its bundle."""
import os
import tempfile
from pathlib import Path
from app_paths import STORAGE, ENGINE_ROOT


def configure_caches():
    defaults={'LOCAL_MUSIC_STORAGE':STORAGE,'LOCAL_MUSIC_ENGINES':ENGINE_ROOT,
              'HF_HOME':STORAGE/'cache'/'huggingface','HF_HUB_CACHE':STORAGE/'cache'/'huggingface'/'hub',
              'UV_DATA_DIR':STORAGE/'uv','UV_CACHE_DIR':STORAGE/'cache'/'uv','UV_PYTHON_INSTALL_DIR':STORAGE/'python',
              'UV_TOOL_DIR':STORAGE/'tools','UV_PYTHON_BIN_DIR':STORAGE/'bin'}
    for key,value in defaults.items():os.environ.setdefault(key,str(value))


def describe():
    import shutil
    parent=STORAGE
    while not parent.exists() and parent!=parent.parent:parent=parent.parent
    try:free=shutil.disk_usage(parent).free
    except OSError:free=None
    return {'root':str(STORAGE),'engines':str(ENGINE_ROOT),'freeBytes':free}


def prepare():
    try:
        STORAGE.mkdir(parents=True,exist_ok=True)
        ENGINE_ROOT.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.write-check-',dir=STORAGE) as folder:
            (Path(folder)/'test').write_text('ok',encoding='utf-8')
    except OSError as error:
        raise RuntimeError('앱이 설치된 드라이브에 준비 파일을 저장할 수 없습니다. '
                           '설치 파일(DMG)에서 실행 중이면 앱을 설치할 드라이브의 폴더로 먼저 복사해 주세요. '
                           '해당 폴더의 쓰기 권한과 드라이브 연결을 확인한 뒤 다시 시도해 주세요. '
                           '저장 위치: '+str(STORAGE)) from error
    configure_caches()
