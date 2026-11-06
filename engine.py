"""Single-worker local generation, durable metadata and subprocess isolation."""
import json
import os
import platform
import re
import subprocess
import threading
import time
import uuid
import wave
import translation
from audio_processing import validate_peak_db, wav_peak_db
from pathlib import Path

from app_paths import ROOT, ENGINE_ROOT, background_options
BASE = ENGINE_ROOT / 'stable-audio-3' / 'optimized'
DATA = Path(os.environ.get('LOCAL_MUSIC_DATA', str(Path.home() / '.local-music-studio')))
GUARD = threading.Lock()
ACTIVE = None
PROCESS = None
CURRENT = None

def engine_paths(backend):
    folder = BASE / ('mlx' if backend == 'apple' else 'tflite')
    python = folder / ('.venv/Scripts/python.exe' if platform.system() == 'Windows' else '.venv/bin/python')
    return folder, python, folder / 'scripts' / ('sa3_mlx.py' if backend == 'apple' else 'sa3_tflite.py')

def song_paths():
    folder = ENGINE_ROOT / 'ace-step'
    python = folder / ('.venv/Scripts/python.exe' if platform.system() == 'Windows' else '.venv/bin/python')
    return folder, python, ROOT / 'runners' / 'song.py'

def ready(backend, model='small-music'):
    if model == 'ace-step':
        folder, python, script = song_paths()
        components = ['acestep-v15-turbo/model.safetensors', 'vae/diffusion_pytorch_model.safetensors', 'Qwen3-Embedding-0.6B/model.safetensors', 'acestep-5Hz-lm-0.6B/model.safetensors']
        return python.exists() and script.exists() and all((folder / 'checkpoints' / x).is_file() for x in components)
    folder, python, script = engine_paths(backend)
    return python.exists() and script.exists()

def save(job):
    target = DATA / 'jobs' / (job['id'] + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
    tmp.replace(target)

def history():
    result=[]
    for path in (DATA / 'jobs').glob('*.json'):
        try:
            j=json.loads(path.read_text(encoding='utf-8'))
            if j['status'] in ('running', 'queued') and j['id'] != ACTIVE:
                j['status']='interrupted'; j['error']='앱이 종료되어 작업이 중단되었습니다.'
            progress = path.with_name(j['id'] + '.progress.json')
            if j['status'] in ('running', 'queued') and progress.exists():
                try:
                    j['phase'] = json.loads(progress.read_text(encoding='utf-8')).get('phase')
                except (OSError, ValueError):
                    pass
            result.append(j)
        except (OSError, ValueError, KeyError):
            continue
    return sorted(result,key=lambda j:j['createdAt'],reverse=True)

def start(settings, prompt, available=None, lyrics='', language='ko', title=''):
    global ACTIVE, CURRENT
    settings={**settings, 'peakDb':validate_peak_db(settings.get('peakDb', -6))}
    if not isinstance(prompt,str) or not 1 <= len(prompt.strip()) <= 2000:
        raise ValueError('음악 설명을 1~2000자로 입력하세요.')
    if not isinstance(title,str) or len(title.strip())>100:
        raise ValueError('제목은 100자 이내로 입력하세요.')
    if translation.has_korean(prompt) and not translation.ready():
        raise ValueError('로컬 한영 번역 모델이 설치되지 않았습니다. setup_translation.py로 설치하거나 음악 설명을 영어로 입력하세요.')
    song = settings['mode'] == 'song'
    if settings['model'] != ('ace-step' if song else 'small-music'):
        raise ValueError('배경음악에는 Small-Music, 보컬 노래에는 ACE-Step을 선택하세요.')
    if song:
        if len(prompt.strip()) > 512:
            raise ValueError('노래의 음악 설명은 512자 이내로 입력하세요.')
        if not isinstance(lyrics, str) or not lyrics.strip() or len(lyrics) > 4000:
            raise ValueError('노래 가사를 1~4000자로 입력하세요.')
        if language not in ('ko', 'en', 'ja', 'zh', 'unknown'):
            raise ValueError('지원하는 보컬 언어를 선택하세요.')
    if not ready(settings['backend'], settings['model']):
        raise ValueError('선택한 실행 방식의 엔진이 설치되지 않았습니다.')
    if settings['backend']=='apple' and not (platform.system()=='Darwin' and platform.machine()=='arm64'):
        raise ValueError('Apple Silicon에서만 사용할 수 있는 실행 방식입니다.')
    if available is not None and available < 2:
        raise ValueError('가용 메모리가 2GB 미만입니다. 다른 앱을 종료한 뒤 다시 시도하세요.')
    with GUARD:
        import installer
        if installer.active():
            raise ValueError('모델 준비가 끝난 뒤 생성할 수 있습니다.')
        if ACTIVE:
            raise ValueError('이미 생성 중입니다. 완료하거나 취소한 후 다시 시도하세요.')
        ident=uuid.uuid4().hex
        job={'id':ident,'createdAt':time.time(),'status':'queued','title':title.strip(),'prompt':prompt.strip(),
             'settings':dict(settings),'runtimeRevision':(ROOT/('song-engine-version.txt' if song else 'engines-version.txt')).read_text(encoding='utf-8').strip(),'seed':int.from_bytes(os.urandom(4),'big') % (2**31), 'elapsedSeconds':None}
        if song:
            job.update(lyrics=lyrics.strip(), language=language, plannerRevision=(ROOT/'song-planner-version.txt').read_text(encoding='utf-8').strip())
        save(job); ACTIVE=ident; CURRENT=job
        threading.Thread(target=run,args=(job,),daemon=True).start()
    return job

def translate_job(job):
    """Finish and release the offline translator before loading a music model."""
    global PROCESS
    if not translation.has_korean(job['prompt']):
        return True
    python, _ = translation.runtime_paths()
    output=DATA/'jobs'/(job['id']+'.translation.json')
    log=DATA/'jobs'/(job['id']+'.translation.log')
    progress=DATA/'jobs'/(job['id']+'.progress.json')
    with log.open('w') as stream:
        with GUARD:
            if job.get('cancelRequested'):return False
            job['status']='running';job['phase']='한글 음악 설명을 영어로 변환하고 있습니다';save(job)
            progress.write_text(json.dumps({'phase':job['phase']},ensure_ascii=False), encoding='utf-8')
            PROCESS=subprocess.Popen([str(python),'-u',str(ROOT/'runners'/'translate.py'),'--request',str(DATA/'jobs'/(job['id']+'.json')),'--out',str(output)],stdout=stream,stderr=subprocess.STDOUT,
                env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1'},**background_options())
        process=PROCESS
        try:
            code=process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill();process.wait()
            raise ValueError('번역 시간이 초과되었습니다. 설명을 줄이거나 영어로 입력해 주세요.')
        finally:
            with GUARD:PROCESS=None
    if job.get('cancelRequested'):return False
    if code:
        raise ValueError('로컬 한영 번역에 실패했습니다. 설명을 간단히 쓰거나 영어로 입력해 주세요.')
    result=json.loads(output.read_text(encoding='utf-8'))
    text=result.get('text')
    if not isinstance(text,str) or not text.strip() or translation.has_korean(text):
        raise ValueError('영어 음악 설명을 만들지 못했습니다. 다시 시도하거나 영어로 입력해 주세요.')
    limit=512 if job['settings']['mode']=='song' else 2000
    if len(text)>limit:
        raise ValueError(f'영어로 변환한 음악 설명이 {limit}자를 넘었습니다. 음악 설명을 줄여 주세요.')
    job['generationPrompt']=text
    job['translation']={'model':result['model'],'revision':result['revision'],'sourceLanguage':'ko','targetLanguage':'en'}
    job['phase']='음악 모델을 준비하고 있습니다'
    progress.unlink(missing_ok=True)
    with GUARD:save(job)
    return True

def run(job):
    global ACTIVE, PROCESS, CURRENT
    started=time.monotonic()
    song = job['settings']['model'] == 'ace-step'
    folder, python, script = song_paths() if song else engine_paths(job['settings']['backend'])
    out=DATA/'audio'/(job['id']+'.wav'); out.parent.mkdir(parents=True,exist_ok=True)
    log=DATA/'jobs'/(job['id']+'.log')
    try:
        if not translate_job(job):
            job['status']='cancelled';return
        with GUARD:
            if job.get('cancelRequested'):
                job['status']='cancelled'; return
            job['status']='running';save(job)
            stream=log.open('w')
            args = ([str(python), '-u', str(script), '--request', str(DATA/'jobs'/(job['id']+'.json')),
                     '--out', str(out), '--progress', str(DATA/'jobs'/(job['id']+'.progress.json'))] if song else
                    [str(python),'-u',str(script),'--dit','sm-music','--decoder','same-s',
                     '--prompt',job.get('generationPrompt',job['prompt']),'--seconds',str(job['settings']['seconds']),
                     '--seed',str(job['seed']),'--out',str(out)])
            if not song and script.name in ('sa3_mlx.py', 'sa3_tflite.py'):
                args=[str(python),'-u',str(ROOT/'runners'/'bgm.py'),'--script',str(script),'--peak-db',str(job['settings']['peakDb']),*args[3:]]
            PROCESS=subprocess.Popen(args,cwd=folder,stdout=stream,stderr=subprocess.STDOUT,
                    env={**os.environ,'HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','HF_HUB_DISABLE_XET':'1',**({'HF_HUB_OFFLINE':'1'} if song else {})},**background_options())
        with stream:
            try:
                code=PROCESS.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                PROCESS.kill(); PROCESS.wait(); raise ValueError('30분 제한을 초과했습니다. 더 짧은 길이로 재시도하세요.')
        if job.get('cancelRequested'):
            job['status']='cancelled'
        elif code:
            job['status']='failed'
            if code < 0:
                job['error']='생성 프로세스가 종료되었습니다. 메모리가 부족할 수 있으니 다른 앱을 닫고 더 짧은 길이로 재시도하세요.'
            else:
                job['error']='엔진 실행에 실패했습니다. 모델 접근 권한·다운로드 상태·메모리를 확인하세요.'
                lines=log.read_text(errors='replace', encoding='utf-8').splitlines()
                if lines:
                    job['errorDetails']=re.sub(r'\x1b\[[0-9;]*m','',lines[-1])[-500:]

        else:
            with wave.open(str(out)) as w:
                duration=w.getnframes()/w.getframerate()
                if abs(duration-job['settings']['seconds'])>1: raise ValueError('결과 길이가 요청과 다릅니다.')
            job['outputPeakDb']=wav_peak_db(out)
            if job['outputPeakDb'] is not None and job['outputPeakDb'] > job['settings'].get('peakDb', -6) + 0.01:
                raise ValueError('출력 최대 게인 검증에 실패했습니다.')
            job['status']='completed'; job['audioUrl']='/audio/'+job['id']+'.wav'
            job['durationSeconds']=round(duration,2)
            plan_path=DATA/'jobs'/(job['id']+'.plan.json')
            if song and plan_path.exists():
                job['composition']=json.loads(plan_path.read_text(encoding='utf-8'))
            text=log.read_text(errors='replace', encoding='utf-8')
            job['includedDownload'] = 'downloading MLX/' in text or 'downloading TFLite/' in text
            text=re.sub(r'\x1b\[[0-9;]*m','',text)
            match=re.search(r'peak RAM\s+([\d.]+)\s*(GB|MB)',text)
            rss = re.search(r'process peak RSS\s+([\d.]+)\s*GB', text)
            if rss: job['processPeakGB'] = float(rss[1])
            if match: job['enginePeakGB']=round(float(match[1])/(1024 if match[2]=='MB' else 1),2)
    except Exception as e:
        job['status']='cancelled' if job.get('cancelRequested') else 'failed'
        if not job.get('cancelRequested'):job['error']=str(e)
    finally:
        if song:
            import shutil
            shutil.rmtree(out.parent/(out.stem+'-work'), ignore_errors=True)
        job['elapsedSeconds']=round(time.monotonic()-started,2)
        job.pop('phase',None)
        with GUARD:
            save(job); ACTIVE=None; PROCESS=None; CURRENT=None

def cancel():
    with GUARD:
        if not ACTIVE: return
        if CURRENT is not None: CURRENT['cancelRequested']=True
        if PROCESS and PROCESS.poll() is None: PROCESS.terminate()

def rename_result(ident, title):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('잘못된 생성 결과 ID입니다.')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
        raise ValueError('제목을 1~100자로 입력하세요.')
    with GUARD:
        if ident == ACTIVE:
            raise ValueError('생성이 끝난 후 제목을 수정할 수 있습니다.')
        record = DATA / 'jobs' / (ident + '.json')
        if not record.exists():
            raise FileNotFoundError('이미 삭제되었거나 존재하지 않는 결과입니다.')
        job = json.loads(record.read_text(encoding='utf-8'))
        job['title'] = title.strip()
        save(job)
        return job

def delete_result(ident):
    """Remove a result from the library, retaining its files in local trash."""
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('잘못된 생성 결과 ID입니다.')
    with GUARD:
        if ident == ACTIVE:
            raise ValueError('생성 중인 작업은 취소 후 삭제할 수 있습니다.')
        record = DATA / 'jobs' / (ident + '.json')
        if not record.exists():
            raise FileNotFoundError('이미 삭제되었거나 존재하지 않는 결과입니다.')
        trash = DATA / 'trash' / ident
        trash.mkdir(parents=True, exist_ok=False)
        moved = []
        try:
            for source in [DATA / 'audio' / (ident + '.wav'), DATA / 'jobs' / (ident + '.log'), DATA / 'jobs' / (ident + '.progress.json'), DATA / 'jobs' / (ident + '.plan.json'), DATA / 'jobs' / (ident + '.translation.json'), DATA / 'jobs' / (ident + '.translation.log'), record]:
                if source.exists():
                    target = trash / source.name
                    source.replace(target)
                    moved.append((source, target))
        except OSError:
            for source, target in reversed(moved):
                target.replace(source)
            trash.rmdir()
            raise
