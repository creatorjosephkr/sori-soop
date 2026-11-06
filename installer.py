"""Sequential first-run preparation, sharing the generation guard."""
import os
import json
import platform
import shutil
import signal
import subprocess
import threading
import storage
from app_paths import ROOT,DATA,ENGINE_ROOT,uv_path

LOCK=threading.Lock()
STATE={'active':False,'component':None,'state':'idle','error':None}
PROCESS=None
SCRIPTS={'bgm':'setup_engine.py','translation':'setup_translation.py','song':'setup_song.py'}

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
        return saved.get('error') if saved.get('storageRoot')==str(storage.STORAGE) else None
    except (OSError,ValueError,AttributeError):return None

def remember(error=None):
    DATA.mkdir(parents=True,exist_ok=True)
    path=DATA/'first-setup.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'error':error,'storageRoot':str(storage.STORAGE)},ensure_ascii=False),encoding='utf-8');tmp.replace(path)

def status():
    import engine,translation
    backend='apple' if platform.system()=='Darwin' and platform.machine().lower() in ('arm64','aarch64') else 'cpu'
    with LOCK:state=dict(STATE)
    if state['state']=='idle' and saved_error():state.update(state='failed',error=saved_error())
    return {**state,'storage':storage.describe(),'autoSetupEnabled':os.environ.get('LOCAL_MUSIC_AUTO_SETUP')!='0','ready':{'bgm':engine.ready(backend) and bgm_weights_ready(backend),'translation':translation.ready(),'song':engine.ready(backend,'ace-step')}}

def start(component):
    import engine
    if component not in (*SCRIPTS,'all','auto'):raise ValueError('준비할 모델을 선택하세요.')
    with engine.GUARD:
        current=status()
        if component=='auto' and (current['active'] or current['state']=='failed' or engine.ACTIVE):return current
        if current['active'] or engine.ACTIVE:raise ValueError('현재 작업이 끝난 뒤 모델을 준비해 주세요.')
        components=[key for key in SCRIPTS if not current['ready'][key]] if component in ('all','auto') else [component]
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
        with LOCK:STATE.update(active=True,component=components[0],state='installing',error=None,step=1,total=len(components))
        threading.Thread(target=run_queue,args=(components,),daemon=True).start()
    return status()

def run_queue(components):
    global PROCESS
    try:
        for index,component in enumerate(components,1):
            with LOCK:
                if STATE['state']=='cancelled':return
                STATE.update(component=component,step=index,total=len(components))
            if shutil.disk_usage(ENGINE_ROOT).free<(16 if component=='song' else 3)*1024**3:
                raise RuntimeError('저장 공간이 부족합니다. 노래는 16GB, 나머지는 3GB 이상의 여유 공간을 확보한 뒤 다시 시도해 주세요.')
            run(component)
            if not status()['ready'][component]:raise RuntimeError('설치 결과를 확인하지 못했습니다. 다시 준비해 주세요.')
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='completed',error=None)
        remember()
    except Exception as error:
        shutdown_process()
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='failed',error=str(error))
        if STATE['state']!='cancelled':remember(str(error))
    finally:
        with LOCK:STATE['active']=False;PROCESS=None

def run(component):
    global PROCESS
    log=DATA/('setup-'+component+'.log')
    env={**os.environ,'LOCAL_MUSIC_RESOURCES':str(ROOT),'LOCAL_MUSIC_ENGINES':str(ENGINE_ROOT),'LOCAL_MUSIC_UV':uv_path(),'HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1'}
    options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
    with log.open('w',encoding='utf-8') as output:
        with LOCK:
            if STATE['state']=='cancelled':return
            PROCESS=subprocess.Popen([uv_path(),'run','--no-project','--python','3.11',str(ROOT/SCRIPTS[component])],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,**options)
            process=PROCESS
        code=process.wait(timeout=5400)
    if code:raise RuntimeError('준비하지 못했습니다. 인터넷 연결과 저장 공간을 확인한 뒤 다시 시도해 주세요.')

def shutdown_process():
    with LOCK:process=PROCESS
    if process and process.poll() is None:
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()

def shutdown():
    with LOCK:
        if STATE['active']:STATE.update(state='cancelled')
    shutdown_process()
