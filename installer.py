"""Sequential first-run preparation, sharing the generation guard."""
import os
import json
import platform
import re
import time
import shutil
import signal
import subprocess
import threading
import storage
from app_paths import ROOT,DATA,ENGINE_ROOT,uv_path,bootstrap_python,background_options

LOCK=threading.Lock()
STATE={'active':False,'component':None,'state':'idle','error':None}
PROCESS=None
SETUP_REVISION='windows-song-runtime-v3'
BASE_COMPONENTS=('bgm','translation','song')
SCRIPTS={'bgm':'setup_engine.py','translation':'setup_translation.py','song':'setup_song.py','song-quality':'setup_song_quality.py'}

def active():
    with LOCK:return STATE['active']

def bgm_weights_ready(backend):
    folder=ENGINE_ROOT/'stable-audio-3'/'optimized'/('mlx' if backend=='apple' else 'tflite')
    files=(['models/mlx/t5gemma_f16.npz','models/mlx/dit_sm-music_f16.npz','models/mlx/same_s_decoder_f32.npz']
           if backend=='apple' else ['models/tflite/t5gemma/encoder_fp16.tflite','models/tflite/sa3-sm-music/dit_w8a8.tflite','models/tflite/same-s/dec_w8a8.tflite'])
    return all((folder/name).is_file() for name in files)

def saved_error():
    try:
        saved=json.loads((DATA/'first-setup.json').read_text(encoding='utf-8'))
        return saved.get('error') if saved.get('storageRoot')==str(storage.STORAGE) and saved.get('setupRevision')==SETUP_REVISION else None
    except (OSError,ValueError,AttributeError):return None

def remember(error=None):
    DATA.mkdir(parents=True,exist_ok=True)
    path=DATA/'first-setup.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'error':error,'storageRoot':str(storage.STORAGE),'setupRevision':SETUP_REVISION},ensure_ascii=False),encoding='utf-8');tmp.replace(path)


def log_tail(component):
    """Read a bounded tail even when installers emit carriage-return progress bars."""
    if component not in SCRIPTS:return {'lines':[],'updatedAt':None}
    try:
        with (DATA/('setup-'+component+'.log')).open('rb') as stream:
            size=stream.seek(0,2);stream.seek(max(0,size-32768))
            raw=stream.read(32768);modified=os.fstat(stream.fileno()).st_mtime
        text=raw.decode('utf-8',errors='replace')
        text=re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|$))','',text)
        text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','',text)
        lines=[line.strip()[:500] for line in text.splitlines() if line.strip()]
        return {'lines':lines[-40:],'updatedAt':modified}
    except OSError:return {'lines':[],'updatedAt':None}

def status():
    import engine,translation
    backend='apple' if platform.system()=='Darwin' and platform.machine().lower() in ('arm64','aarch64') else 'cpu'
    with LOCK:state=dict(STATE)
    if state['state']=='idle' and saved_error():state.update(state='failed',error=saved_error())
    log=log_tail(state.get('component'))
    now=time.time()
    return {**state,'log':log,'elapsedSeconds':max(0,int(now-state.get('startedAt',now))),'quietSeconds':max(0,int(now-(log['updatedAt'] or state.get('componentStartedAt',now)))),'storage':storage.describe(),'autoSetupEnabled':os.environ.get('LOCAL_MUSIC_AUTO_SETUP')!='0','optionalReady':{'song-quality':engine.planner_ready('quality')},'ready':{'bgm':engine.ready(backend) and bgm_weights_ready(backend),'translation':translation.ready(),'song':engine.ready(backend,'ace-step')}}

def start(component):
    import engine
    if component not in (*SCRIPTS,'all','auto'):raise ValueError('준비할 모델을 선택하세요.')
    with engine.GUARD:
        current=status()
        if component=='auto' and (current['active'] or current['state']=='failed' or engine.ACTIVE):return current
        if current['active'] or engine.ACTIVE:raise ValueError('현재 작업이 끝난 뒤 모델을 준비해 주세요.')
        components=[key for key in BASE_COMPONENTS if not current['ready'][key]] if component in ('all','auto') else [component]
        if component=='song-quality' and not current['ready'].get('song'):raise ValueError('노래 기본 실행 준비를 먼저 완료해 주세요.')
        if not components:return current
        DATA.mkdir(parents=True,exist_ok=True)
        try:
            storage.prepare()
            uv_path()
        except (OSError,RuntimeError) as error:
            remember(str(error))
            with LOCK:STATE.update(state='failed',error=str(error))
            raise
        remember()
        with LOCK:STATE.update(active=True,component=components[0],state='installing',error=None,step=1,total=len(components),startedAt=time.time(),componentStartedAt=time.time())
        threading.Thread(target=run_queue,args=(components,),daemon=True).start()
    return status()

def run_queue(components):
    global PROCESS
    try:
        for index,component in enumerate(components,1):
            with LOCK:
                if STATE['state']=='cancelled':return
                STATE.update(component=component,step=index,total=len(components),componentStartedAt=time.time())
            import song_runtime
            required=16 if component=='song' and not song_runtime.models_ready(ENGINE_ROOT/'ace-step') else 3
            if component=='song-quality':required=5
            if shutil.disk_usage(ENGINE_ROOT).free<required*1024**3:
                raise RuntimeError('저장 공간이 부족합니다. 노래는 16GB, 품질 모델은 5GB, 나머지는 3GB 이상의 여유 공간을 확보한 뒤 다시 시도해 주세요.')
            run(component)
            current=status()
            ready=current.get('optionalReady',{}).get(component) if component=='song-quality' else current['ready'][component]
            if not ready:raise RuntimeError('설치 결과를 확인하지 못했습니다. 다시 준비해 주세요.')
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='completed',error=None)
        remember()
    except Exception as error:
        shutdown_process()
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='failed',error=str(error))
        if STATE['state']!='cancelled' and 'song-quality' not in components:remember(str(error))
    finally:
        with LOCK:STATE['active']=False;PROCESS=None

def run(component):
    global PROCESS
    log=DATA/('setup-'+component+'.log')
    env={**os.environ,'LOCAL_MUSIC_RESOURCES':str(ROOT),'LOCAL_MUSIC_ENGINES':str(ENGINE_ROOT),'LOCAL_MUSIC_UV':uv_path(),'HF_HUB_DISABLE_TELEMETRY':'1','HF_HUB_DISABLE_XET':'1','HF_HUB_DOWNLOAD_TIMEOUT':'30','HF_HUB_ETAG_TIMEOUT':'15','DO_NOT_TRACK':'1','PYTHONUNBUFFERED':'1','HF_HUB_DISABLE_PROGRESS_BARS':'0','TQDM_MININTERVAL':'1'}
    python=bootstrap_python()
    command=[python,str(ROOT/SCRIPTS[component])] if python else [uv_path(),'run','--no-project','--python','3.11',str(ROOT/SCRIPTS[component])]
    if python:
        env.update(LOCAL_MUSIC_BOOTSTRAP_PYTHON=python,UV_PYTHON_DOWNLOADS='never',UV_NO_MANAGED_PYTHON='1',UV_NO_CONFIG='1',UV_LINK_MODE='copy',PYTHONDONTWRITEBYTECODE='1')
        for key in ('PYTHONHOME','PYTHONPATH','VIRTUAL_ENV'):env.pop(key,None)
    options=background_options(group=True)
    with log.open('w',encoding='utf-8',buffering=1) as output:
        output.write('준비 작업을 시작합니다. 실행 환경과 필요한 파일을 확인하고 있습니다.\n');output.flush()
        with LOCK:
            if STATE['state']=='cancelled':return
            PROCESS=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,**options)
            process=PROCESS
        code=process.wait(timeout=5400)
    if code:raise RuntimeError('실행 환경 준비 또는 호환성 검사에 실패했습니다. 아래 설치 로그를 확인한 뒤 다시 시도해 주세요.')

def shutdown_process():
    with LOCK:process=PROCESS
    if process and process.poll() is None:
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**background_options())
        else:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()

def shutdown():
    with LOCK:
        if STATE['active']:STATE.update(state='cancelled')
    shutdown_process()
