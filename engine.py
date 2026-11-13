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
import song_runtime
import song_duration
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

def planner_ready(quality='light'):return song_runtime.planner_ready(ENGINE_ROOT/'ace-step',quality)

def sa3_model_ready(backend,model='small-music'):
    import installer
    return ready(backend,'small-music') and installer.bgm_weights_ready(backend,model)

def ready(backend, model='small-music'):
    if model == 'ace-step':
        folder, python, script = song_paths()
        return python.exists() and script.exists() and song_runtime.models_ready(folder) and (platform.system()!='Windows' or song_runtime.ready(folder, backend))
    folder, python, script = engine_paths(backend)
    return python.exists() and script.exists()

def save(job):
    target = DATA / 'jobs' / (job['id'] + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
    tmp.replace(target)

MIGRATED = False

def migrate_legacy_audio():
    global MIGRATED
    if MIGRATED:
        return
    MIGRATED = True
    audio_dir = DATA / 'audio'
    if not audio_dir.is_dir():
        return
    marker = '소리숲 제작'.encode('utf-16-le')
    for wav_path in audio_dir.glob('*.wav'):
        ident = wav_path.stem
        if not re.fullmatch(r'[a-f0-9]{32}', ident):
            continue
        try:
            raw = wav_path.read_bytes()
            if b'id3 ' not in raw or b'INFO' not in raw or marker not in raw:
                title = ''
                rec = DATA / 'jobs' / f'{ident}.json'
                if rec.is_file():
                    try:
                        j = json.loads(rec.read_text(encoding='utf-8'))
                        title = (j.get('title') or j.get('prompt') or '').strip()
                    except Exception:
                        pass
                from audio_processing import apply_wav_metadata
                apply_wav_metadata(wav_path, title=title)
        except Exception:
            pass
    for mp3_path in audio_dir.glob('*.mp3'):
        try:
            raw = mp3_path.read_bytes()[:1024]
            if not raw.startswith(b'ID3') or marker not in raw:
                mp3_path.unlink(missing_ok=True)
        except Exception:
            pass

def history():
    global MIGRATED
    if not MIGRATED:
        threading.Thread(target=migrate_legacy_audio, daemon=True).start()
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

def start(settings, prompt, available=None, lyrics='', language='ko', title='', negative_prompt=''):
    global ACTIVE, CURRENT
    settings={**settings, 'peakDb':validate_peak_db(settings.get('peakDb', -8))}
    if not isinstance(prompt,str) or not 1 <= len(prompt.strip()) <= 2000:
        raise ValueError('음악 설명을 1~2000자로 입력하세요.')
    if not isinstance(title,str) or len(title.strip())>100:
        raise ValueError('제목은 100자 이내로 입력하세요.')
    if not isinstance(negative_prompt,str) or len(negative_prompt.strip())>1000:
        raise ValueError('네거티브 프롬프트는 1000자 이내로 입력하세요.')
    if (translation.has_korean(prompt) or translation.has_korean(negative_prompt)) and not translation.ready():
        raise ValueError('로컬 한영 번역 모델이 설치되지 않았습니다. setup_translation.py로 설치하거나 음악 설명을 영어로 입력하세요.')
    mode = settings['mode']
    song = mode == 'song'
    instrumental = song and settings.get('instrumental', False)
    if type(instrumental) is not bool:
        raise ValueError('Instrumental 옵션을 확인하세요.')
    if instrumental:
        if song_duration.automatic(settings):
            raise ValueError('연주곡은 길이를 직접 지정해 주세요.')
        lyrics = ''
        language = 'unknown'
    if song and settings['model'] != 'ace-step':
        raise ValueError('배경음악에는 Small-Music, 보컬 노래에는 ACE-Step을 선택하세요.')
    if mode == 'bgm' and settings['model'] not in ('small-music', 'medium'):
        raise ValueError('배경음악에는 Small-Music 또는 Medium 모델을 선택하세요.')
    if mode == 'sfx' and settings['model'] != 'small-sfx':
        raise ValueError('효과음에는 Small-SFX 모델을 선택하세요.')
    if settings['model'] == 'medium' and not sa3_model_ready(settings['backend'], 'medium'):
        raise ValueError('고품질 배경음악(Medium) 모델을 먼저 준비해 주세요. 음악 모델 설정 아래의 설치 버튼을 누르세요.')
    if settings['model'] == 'small-sfx' and not sa3_model_ready(settings['backend'], 'small-sfx'):
        raise ValueError('효과음(Small-SFX) 모델을 먼저 준비해 주세요. 음악 모델 설정 아래의 설치 버튼을 누르세요.')
    if song:
        if settings.get('songQuality','light') not in song_runtime.PLANNERS:raise ValueError('노래 품질 모델을 확인하세요.')
        import song_expert
        settings['songExpert']=song_expert.normalize(settings.get('songExpert'))
        if settings.get('songQuality')=='quality':
            if not planner_ready('quality'):raise ValueError('품질 우선 모델을 먼저 준비해 주세요. 노래 품질 설정 아래의 준비 버튼을 누르세요.')
            minimum=4 if settings['backend']=='apple' else 8
            if available is not None and available<minimum:raise ValueError(f'품질 모델을 위해 가용 메모리 {minimum}GB 이상을 확보하거나 가벼운 모델을 선택해 주세요.')
        song_duration.explicit_bpm(prompt)
        if not instrumental and (not isinstance(lyrics, str) or not lyrics.strip() or len(lyrics) > 4000):
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
        if negative_prompt.strip():
            job['negativePrompt']=negative_prompt.strip()
        if song:
            job.update(lyrics=lyrics.strip(), language=language, plannerRevision=(ROOT/'song-planner-version.txt').read_text(encoding='utf-8').strip())
        save(job); ACTIVE=ident; CURRENT=job
        threading.Thread(target=run,args=(job,),daemon=True).start()
    return job

def translate_job(job):
    """Finish and release the offline translator before loading a music model."""
    global PROCESS
    source=job['prompt']
    neg_source=job.get('negativePrompt','')
    has_ko_prompt=translation.has_korean(source)
    has_ko_neg=translation.has_korean(neg_source)
    if not has_ko_prompt and not has_ko_neg:
        if job['settings']['mode']!='song' and len(source)>2000:raise ValueError('음악 설명이 너무 깁니다. 설명을 줄여 주세요.')
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
    if has_ko_prompt:
        text=result.get('text')
        if not isinstance(text,str) or not text.strip() or translation.has_korean(text):
            raise ValueError('영어 음악 설명을 만들지 못했습니다. 다시 시도하거나 영어로 입력해 주세요.')
        if job['settings']['mode']!='song' and len(text)>2000:
            raise ValueError('영어로 변환한 음악 설명이 2000자를 넘었습니다. 음악 설명을 줄여 주세요.')
        job['generationPrompt']=text
    if has_ko_neg:
        neg_text=result.get('negativeText')
        if not isinstance(neg_text,str) or not neg_text.strip() or translation.has_korean(neg_text):
            raise ValueError('영어 네거티브 프롬프트를 만들지 못했습니다. 다시 시도하거나 영어로 입력해 주세요.')
        job['generationNegativePrompt']=neg_text
    job['translation']={'model':result['model'],'revision':result['revision'],'sourceLanguage':'ko','targetLanguage':'en'}
    job['phase']='음악 모델을 준비하고 있습니다'
    progress.unlink(missing_ok=True)
    with GUARD:save(job)
    return True

def generation_failure(code, log_text, windows=False):
    """Keep native Windows exits distinct from ordinary Python exceptions."""
    lines=re.sub(r'\x1b\[[0-9;]*m','',log_text).splitlines()
    tail='\n'.join(lines[-60:])[-12000:]
    status=code & 0xffffffff
    label=f'0x{status:08X}' if windows else str(code)
    if windows and status in (0xC0000017,0xC000012D,0xC000012C):
        message='Windows에서 사용 가능한 메모리 또는 가상 메모리가 부족해 생성이 중단되었습니다. 다른 앱을 닫고 Windows 가상 메모리를 시스템 관리 크기로 설정한 뒤 다시 시도하세요.'
    elif windows and status==0xC000001D:
        message='CPU 명령을 실행하지 못해 생성 엔진이 종료되었습니다. CPU와 실행 패키지의 호환성 확인이 필요합니다.'
    elif windows and status==0xC0000005:
        message='생성 엔진에서 메모리 접근 오류가 발생했습니다. 종료 코드와 아래 로그로 원인을 확인해야 합니다.'
    elif windows and status in (0xC0000135,0xC0000139):
        message='생성 엔진의 DLL을 불러오지 못했습니다. 실행 패키지 호환성 확인이 필요합니다.'
    elif 'out of memory' in tail.lower() or 'cannot allocate memory' in tail.lower() or 'not enough memory' in tail.lower():
        message='음악 생성에 필요한 메모리를 확보하지 못했습니다. 다른 앱을 닫고 더 짧은 길이로 재시도하세요.'
    elif code<0 and not windows:
        message='생성 프로세스가 종료되었습니다. 메모리가 부족할 수 있으니 다른 앱을 닫고 더 짧은 길이로 재시도하세요.'
    else:
        message='엔진 실행에 실패했습니다. 아래 종료 코드와 생성 로그를 확인해 주세요.'
    return message,f'종료 코드: {label} ({code})\n'+tail


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
            model_id = job['settings']['model']
            dit = {'small-music': 'sm-music', 'medium': 'medium', 'small-sfx': 'sm-sfx'}.get(model_id, 'sm-music')
            decoder = 'same-l' if model_id == 'medium' and job['settings']['backend'] == 'apple' else 'same-s'
            neg_prompt = (job.get('generationNegativePrompt') or job.get('negativePrompt') or '').strip()
            neg_args = ['--negative-prompt', neg_prompt, '--cfg', '2.0'] if neg_prompt else []
            args = ([str(python), '-u', str(script), '--request', str(DATA/'jobs'/(job['id']+'.json')),
                     '--out', str(out), '--progress', str(DATA/'jobs'/(job['id']+'.progress.json'))] if song else
                    [str(python),'-u',str(script),'--dit',dit,'--decoder',decoder,
                     '--prompt',job.get('generationPrompt',job['prompt']),'--seconds',str(job['settings']['seconds']),
                     '--seed',str(job['seed']),'--out',str(out),*neg_args])
            if not song and script.name in ('sa3_mlx.py', 'sa3_tflite.py'):
                args=[str(python),'-u',str(ROOT/'runners'/'bgm.py'),'--script',str(script),'--peak-db',str(job['settings']['peakDb']),*args[3:]]
        with stream:
            for phase in (('plan','render') if song and platform.system()=='Windows' else (None,)):
                with GUARD:
                    if job.get('cancelRequested'):break
                    command=args+['--phase',phase] if phase else args
                    PROCESS=subprocess.Popen(command,cwd=folder,stdout=stream,stderr=subprocess.STDOUT,
                        env={**os.environ,'HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','HF_HUB_DISABLE_XET':'1',**({'HF_HUB_OFFLINE':'1'} if song else {})},**background_options())
                try:
                    code=PROCESS.wait(timeout=max(.01,1800-(time.monotonic()-started)))
                except subprocess.TimeoutExpired:
                    PROCESS.kill(); PROCESS.wait(); raise ValueError('30분 제한을 초과했습니다. 더 짧은 길이로 재시도하세요.')
                if code:break
        if job.get('cancelRequested'):
            job['status']='cancelled'
        elif code:
            job['status']='failed'
            job['exitCode']=code
            job['error'],job['errorDetails']=generation_failure(code,log.read_text(errors='replace',encoding='utf-8'),platform.system()=='Windows')
            check_path=DATA/'jobs'/(job['id']+'.input-check.json')
            if song and check_path.exists():
                check=json.loads(check_path.read_text(encoding='utf-8'))
                if not check.get('ok') and check.get('error'):job['error']=check['error']

        else:
            with wave.open(str(out)) as w:
                duration=w.getnframes()/w.getframerate()
                if song_duration.automatic(job['settings']):
                    if not 10<=duration<=600:raise ValueError('자동으로 생성한 노래 길이가 지원 범위를 벗어났습니다.')
                elif abs(duration-job['settings']['seconds'])>1:raise ValueError('결과 길이가 요청과 다릅니다.')
            job['outputPeakDb']=wav_peak_db(out)
            if job['outputPeakDb'] is not None and job['outputPeakDb'] > job['settings'].get('peakDb', -8) + 0.01:
                raise ValueError('출력 최대 게인 검증에 실패했습니다.')
            from audio_processing import apply_wav_metadata
            apply_wav_metadata(out, title=job.get('title') or job.get('prompt'))
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
            plan_path=DATA/'jobs'/(job['id']+'.plan.json')
            try:
                if plan_path.exists():job['composition']=json.loads(plan_path.read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
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
        audio = DATA / 'audio' / (ident + '.wav')
        if audio.is_file():
            from audio_processing import apply_wav_metadata
            apply_wav_metadata(audio, title=job['title'])
        mp3 = DATA / 'audio' / (ident + '.mp3')
        mp3.unlink(missing_ok=True)
        return job

def prepare_wav(ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('잘못된 생성 결과 ID입니다.')
    with GUARD:
        record = DATA / 'jobs' / (ident + '.json')
        source = DATA / 'audio' / (ident + '.wav')
        if not source.is_file():
            raise FileNotFoundError('이미 삭제되었거나 존재하지 않는 결과입니다.')
        title = ''
        if record.is_file():
            try:
                job = json.loads(record.read_text(encoding='utf-8'))
                title = (job.get('title') or job.get('prompt') or '').strip()
            except (OSError, ValueError):
                pass
        try:
            raw = source.read_bytes()
            marker = '소리숲 제작'.encode('utf-16-le')
            if b'id3 ' not in raw or b'INFO' not in raw or marker not in raw:
                from audio_processing import apply_wav_metadata
                apply_wav_metadata(source, title=title)
        except Exception:
            pass
        return source

def export_mp3(ident):
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('잘못된 생성 결과 ID입니다.')
    # Serialize exports and deletion so no partial or orphaned cache is published.
    with GUARD:
        record = DATA / 'jobs' / (ident + '.json')
        source = DATA / 'audio' / (ident + '.wav')
        target = source.with_suffix('.mp3')
        if not record.is_file() or not source.is_file():
            raise FileNotFoundError('이미 삭제되었거나 존재하지 않는 결과입니다.')
        job = json.loads(record.read_text(encoding='utf-8'))
        if job.get('status') != 'completed' or ident == ACTIVE:
            raise ValueError('생성이 완료된 결과만 MP3로 다운로드할 수 있습니다.')
        title = (job.get('title') or job.get('prompt') or '').strip()
        marker = '소리숲 제작'.encode('utf-16-le')
        needs_build = not target.is_file() or target.stat().st_mtime_ns < source.stat().st_mtime_ns or not target.stat().st_size
        if not needs_build:
            try:
                raw_head = target.read_bytes()[:1024]
                if not raw_head.startswith(b'ID3') or marker not in raw_head:
                    needs_build = True
            except OSError:
                needs_build = True
        if needs_build:
            from audio_export import write_mp3
            write_mp3(source, target, title=title)
        return target


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
            for source in [DATA / 'audio' / (ident + '.wav'), DATA / 'audio' / (ident + '.mp3'), DATA / 'jobs' / (ident + '.log'), DATA / 'jobs' / (ident + '.progress.json'), DATA / 'jobs' / (ident + '.plan.json'), DATA / 'jobs' / (ident + '.translation.json'), DATA / 'jobs' / (ident + '.translation.log'), record]:
                if source.exists():
                    target = trash / source.name
                    source.replace(target)
                    moved.append((source, target))
        except OSError:
            for source, target in reversed(moved):
                target.replace(source)
            trash.rmdir()
            raise


def _trash_entries():
    root = DATA / 'trash'
    if not root.exists() or root.is_symlink():
        return []
    entries = []
    for folder in root.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[a-f0-9]{32}', folder.name):
            continue
        record = folder / (folder.name + '.json')
        try:
            job = json.loads(record.read_text(encoding='utf-8')) if not record.is_symlink() else {}
            if not isinstance(job, dict):job = {}
        except (OSError, ValueError):
            job = {}
        settings = job.get('settings') if isinstance(job.get('settings'), dict) else {}
        mode = settings.get('mode', 'bgm') if job else 'unknown'
        kind = ('instrumental' if settings.get('instrumental') else 'song') if mode == 'song' else mode
        files = [path for path in folder.rglob('*') if not path.is_symlink() and path.is_file()]
        entries.append({'id': folder.name, 'title': str(job.get('title') or job.get('prompt') or '제목 없는 결과'),
                        'kind': kind, 'deletedAt': folder.stat().st_mtime,
                        'bytes': sum(path.stat().st_size for path in files)})
    return sorted(entries, key=lambda item:item['deletedAt'], reverse=True)


def trash_history():
    with GUARD:
        return _trash_entries()


def empty_trash(ids):
    """Permanently remove only the archived entries confirmed by the caller."""
    import shutil
    if not isinstance(ids, list) or not ids or len(ids) > 10000 or any(not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident) for ident in ids):
        raise ValueError('비울 휴지통 항목을 확인하세요.')
    with GUARD:
        root = DATA / 'trash'
        if root.is_symlink():raise ValueError('휴지통 경로를 확인하세요.')
        count = 0
        errors = []
        for ident in dict.fromkeys(ids):
            target = root / ident
            if target.is_symlink():
                errors.append(ident)
                continue
            if not target.exists():continue
            try:
                shutil.rmtree(target)
                count += 1
            except OSError:
                errors.append(ident)
        return {'ok': not errors, 'count': count, 'errors': errors}
