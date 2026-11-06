"""Explicit first-run preparation, with one install/generation operation at a time."""
import os
import platform
import shutil
import signal
import subprocess
import threading
from app_paths import ROOT,DATA,ENGINE_ROOT,uv_path

LOCK=threading.Lock()
STATE={'active':False,'component':None,'state':'idle','error':None}
PROCESS=None
SCRIPTS={'bgm':'setup_engine.py','translation':'setup_translation.py','song':'setup_song.py'}

def active():
    with LOCK:return STATE['active']

def status():
    import engine,translation
    backend='apple' if platform.system()=='Darwin' and platform.machine()=='arm64' else 'cpu'
    with LOCK:state=dict(STATE)
    return {**state,'ready':{'bgm':engine.ready(backend),'translation':translation.ready(),'song':engine.ready(backend,'ace-step')}}

def start(component):
    import engine
    if component not in SCRIPTS:raise ValueError('준비할 모델을 선택하세요.')
    DATA.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(DATA).free<(16 if component=='song' else 3)*1024**3:
        raise ValueError('저장 공간이 부족합니다. 노래는 16GB, 나머지는 3GB 이상의 여유 공간을 확보해 주세요.')
    uv_path()
    with engine.GUARD:
        with LOCK:
            if STATE['active'] or engine.ACTIVE:raise ValueError('현재 작업이 끝난 뒤 모델을 준비해 주세요.')
            STATE.update(active=True,component=component,state='installing',error=None)
        threading.Thread(target=run,args=(component,),daemon=True).start()
    return status()

def run(component):
    global PROCESS
    log=DATA/('setup-'+component+'.log')
    try:
        env={**os.environ,'LOCAL_MUSIC_RESOURCES':str(ROOT),'LOCAL_MUSIC_ENGINES':str(ENGINE_ROOT),'LOCAL_MUSIC_UV':uv_path(),'HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1'}
        options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
        with log.open('w',encoding='utf-8') as output:
            with LOCK:
                if STATE['state']=='cancelled':return
                PROCESS=subprocess.Popen([uv_path(),'run','--no-project','--python','3.11',str(ROOT/SCRIPTS[component])],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,**options)
                process=PROCESS
            code=process.wait(timeout=5400)
        if code:raise RuntimeError('설치하지 못했습니다. 인터넷 연결과 저장 공간을 확인한 뒤 다시 시도해 주세요.')
        if not status()['ready'][component]:raise RuntimeError('설치 결과를 확인하지 못했습니다. 다시 준비해 주세요.')
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='completed',error=None)
    except Exception as error:
        shutdown_process()
        with LOCK:
            if STATE['state']!='cancelled':STATE.update(state='failed',error=str(error))
    finally:
        with LOCK:STATE['active']=False;PROCESS=None

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
