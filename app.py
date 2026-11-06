import json
import engine
import translation
import installer
import updates
import song_duration
from app_paths import background_options
from audio_processing import validate_peak_db
import os
import platform
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('LOCAL_MUSIC_DATA', str(Path.home() / '.local-music-studio')))
LOCK = threading.Lock()
PAYPAL_SPONSOR_URL = 'https://www.paypal.com/paypalme/tech1010?locale.x=ko_KR&country.x=KR'

def open_paypal():
    open_external(PAYPAL_SPONSOR_URL)

def open_external(url):
    """Open a server-validated URL with the OS default browser."""
    system = platform.system()
    if system == 'Windows':
        os.startfile(url)
    else:
        subprocess.run(['open' if system == 'Darwin' else 'xdg-open', url], check=True, timeout=10)

MODELS = {
    'small-music': {'name': 'Stable Audio 3 Small-Music', 'maxSeconds': 120, 'vocals': False},
    'ace-step': {'name': 'ACE-Step 1.5', 'maxSeconds': 600, 'vocals': True},
}

def command(args):
    try:
        return subprocess.check_output(args, timeout=5, stderr=subprocess.DEVNULL, text=True,**background_options()).strip()
    except (OSError, subprocess.SubprocessError):
        return ''

def diagnose():
    system = platform.system()
    total = available = None
    chip = platform.processor() or platform.machine()
    gpu = []
    if system == 'Darwin':
        chip = command(['sysctl', '-n', 'machdep.cpu.brand_string']) or chip
        raw = command(['sysctl', '-n', 'hw.memsize'])
        total = int(raw) if raw.isdigit() else None
        vm = command(['vm_stat'])
        try:
            import re
            page = int(re.search(r'page size of (\d+) bytes', vm)[1])
            counts = dict(re.findall(r'([^\n:]+):\s+(\d+)', vm))
            available = sum(int(counts.get(k, 0)) for k in ('Pages free', 'Pages inactive', 'Pages speculative')) * page
        except (TypeError, ValueError):
            pass
    elif system == 'Linux':
        try:
            values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text(encoding='utf-8').splitlines())
            total = int(values['MemTotal'].split()[0]) * 1024
            available = int(values['MemAvailable'].split()[0]) * 1024
        except (OSError, KeyError, ValueError):
            pass
    elif system == 'Windows':
        try:
            import ctypes
            class Memory(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(k, ctypes.c_ulonglong) for k in ('total', 'available', 'pageTotal', 'pageAvailable', 'virtualTotal', 'virtualAvailable', 'extended')]
            mem = Memory()
            mem.length = ctypes.sizeof(mem)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                total, available = mem.total, mem.available
        except (AttributeError, OSError):
            pass
    raw_gpu = command(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'])
    for line in raw_gpu.splitlines():
        try:
            name, size = line.rsplit(',', 1)
            gpu.append({'name': name.strip(), 'vramGB': round(float(size) / 1024, 1)})
        except ValueError:
            pass
    apple = system == 'Darwin' and platform.machine() == 'arm64'
    return {'os': system, 'chip': chip, 'appleSilicon': apple, 'cpuCores': os.cpu_count(),
            'ramGB': round(total / 1024**3, 1) if total else None,
            'availableGB': round(available / 1024**3, 1) if available is not None else None,
            'availableNote': 'OS가 보고한 가용량의 근사치이며 실제 생성 메모리 한도와 다릅니다.',
            'gpu': gpu, 'diskFreeGB': round(shutil.disk_usage(ROOT).free / 1024**3, 1), 'checkedAt': time.time()}

def recommend(info, mode='bgm'):
    ram = info.get('ramGB') or 0
    free = info.get('availableGB')
    vram = max((g['vramGB'] for g in info.get('gpu', [])), default=0)
    song = mode == 'song'
    model = 'ace-step' if song else 'small-music'
    limited = ram < 12 or (free is not None and free < 4)
    seconds = 30 if limited or song else 60
    warnings = []
    if song:
        warnings.append('가사를 직접 입력하세요. 짧은 노래부터 시작하고, 발음과 가사 반영 여부를 들어보세요.')
        if ram < 12:
            warnings.append('8GB급 환경에서는 노래 모델의 안정적인 실행을 보장할 수 없습니다.')
        if not info.get('appleSilicon') and vram < 6:
            warnings.append('GPU 호환성 확인이 필요합니다. CPU 노래 생성은 속도와 메모리를 별도 검증해야 합니다.')
    if free is not None and free < 3:
        warnings.append('현재 가용 메모리가 적습니다. 다른 앱을 종료한 뒤 다시 진단하세요.')
    return {'model': model, 'backend': 'apple' if info.get('appleSilicon') else 'cpu',
            'seconds': seconds, 'recommendedSeconds': seconds, 'batchSize': 1,
            'basis': '사양 기반의 보수적인 초기값 · 성능 실측 전', 'warnings': warnings,
            'gpuNote': 'NVIDIA 장치 발견 여부는 실행 라이브러리 호환성을 보장하지 않습니다.',
            'estimatedTime': None}

def read_settings():
    try:
        return json.loads((DATA / 'settings.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'policy': 'auto', 'mode': 'bgm'}

def validate(settings):
    settings=dict(settings)
    if settings.get('policy') not in ('auto', 'fixed', 'manual') or settings.get('mode') not in ('bgm', 'song'):
        raise ValueError('설정 방식 또는 제작 모드를 확인하세요.')
    duration_mode=settings.get('durationMode','manual')
    if duration_mode not in ('manual','auto') or (duration_mode=='auto' and settings['mode']!='song'):
        raise ValueError('자동 길이는 노래 만들기에서만 사용할 수 있습니다.')
    auto_length=song_duration.automatic(settings)
    if auto_length:settings['seconds']=None
    if settings['policy'] != 'auto':
        model = settings.get('model')
        if model not in MODELS:
            raise ValueError('지원하지 않는 모델입니다.')
        if settings['mode'] == 'song' and not MODELS[model]['vocals']:
            raise ValueError('이 모델은 가사 기반 노래를 지원하지 않습니다.')
        seconds = settings.get('seconds')
        if not auto_length and (type(seconds) is not int or not 10 <= seconds <= MODELS[model]['maxSeconds']):
            raise ValueError('음악 길이가 모델 지원 범위를 벗어났습니다.')
        if settings.get('backend') not in ('cpu', 'apple'):
            raise ValueError('실행 방식을 확인하세요.')
    if settings['policy'] == 'auto' and 'seconds' in settings:
        model = 'ace-step' if settings['mode'] == 'song' else 'small-music'
        seconds = settings['seconds']
        if not auto_length and (type(seconds) is not int or not 10 <= seconds <= MODELS[model]['maxSeconds']):
            raise ValueError('음악 길이가 모델 지원 범위를 벗어났습니다.')
    if type(settings.get('instrumentalEdges',True)) is not bool:raise ValueError('Intro·Outro 연주 설정을 확인하세요.')
    validate_peak_db(settings.get('peakDb', -6))
    return {k: settings[k] for k in ('policy', 'mode', 'model', 'seconds', 'backend', 'peakDb', 'durationMode', 'instrumentalEdges') if k in settings}

def resolve_generation_settings(settings, info):
    resolved = dict(settings)
    if resolved['policy'] == 'auto':
        rec = recommend(info, resolved['mode'])
        resolved.update({key: rec[key] for key in ('model', 'backend')})
        if not song_duration.automatic(resolved):resolved.setdefault('seconds', rec['seconds'])
    return resolved


class Handler(BaseHTTPRequestHandler):
    def reply(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def local_host(self):
        return self.headers.get('Host', '').split(':')[0] in ('127.0.0.1', 'localhost')

    def do_GET(self):
        if not self.local_host():
            return self.reply({'error': '로컬 주소로 접속하세요.'}, 403)
        if self.path == '/api/session' and hasattr(self.server,'studio_session'):
            return self.reply(self.server.studio_session)
        if self.path == '/api/setup':
            return self.reply(installer.status())
        if self.path == '/api/jobs':
            return self.reply({'jobs': engine.history()})
        if self.path.startswith('/audio/'):
            import re
            if not re.fullmatch(r'/audio/[a-f0-9]{32}\.wav', self.path):
                return self.reply({'error': '잘못된 파일 경로'}, 404)
            path = engine.DATA / 'audio' / self.path.rsplit('/', 1)[1]
            if not path.exists():
                return self.reply({'error': '파일을 찾을 수 없습니다.'}, 404)
            return self.serve_audio(path)
        if self.path == '/api/status':
            info = diagnose()
            settings = read_settings()
            return self.reply({'system': info, 'settings': settings, 'translationReady': translation.ready(), 'recommendation': recommend(info, settings.get('mode', 'bgm')), 'models': MODELS, 'engineReady': engine.ready('apple' if info['appleSilicon'] else 'cpu'), 'engines': {b: engine.ready(b) for b in ('apple', 'cpu')}, 'songEngines': {b: engine.ready(b, 'ace-step') for b in ('apple', 'cpu')}})
        paths = {'/': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js', '/presets.js': 'presets.js', '/player.js': 'player.js', '/icons.js': 'icons.js', '/setup.js': 'setup.js', '/updates.js': 'updates.js', '/fonts/NotoSansKR-Variable.ttf': 'fonts/NotoSansKR-Variable.ttf', '/icons/sorisup.svg': 'icons/sorisup.svg', '/icons/chatgpt.svg': 'icons/chatgpt.svg', '/icons/claude.ico': 'icons/claude.ico', '/icons/gemini.png': 'icons/gemini.png'}
        paths.update({'/spon/'+name: '../spon/'+name for name in ('spon.svg', 'kakaobank.png', 'paypal.png')})
        if self.path not in paths:
            return self.reply({'error': '찾을 수 없습니다.'}, 404)
        path = ROOT / 'web' / paths[self.path]
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html; charset=utf-8', 'css': 'text/css', 'js': 'text/javascript', 'svg': 'image/svg+xml', 'ico': 'image/x-icon', 'png': 'image/png', 'ttf': 'font/ttf'}[path.suffix[1:]])
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def serve_audio(self, path):
        import re
        size=path.stat().st_size
        start,end=0,size-1
        requested=self.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            if not match or not any(match.groups()):
                start=size
            elif not match[1]:
                length=int(match[2]);start=max(0,size-length)
                if length==0:start=size
            else:
                start=int(match[1]);end=min(int(match[2]),size-1) if match[2] else size-1
            if start>=size or start>end:
                self.send_response(416)
                self.send_header('Content-Range',f'bytes */{size}')
                self.send_header('Content-Length','0');self.end_headers();return
        self.send_response(206 if requested else 200)
        self.send_header('Content-Type','audio/wav')
        self.send_header('Accept-Ranges','bytes')
        if requested:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(max(0,end-start+1)))
        self.end_headers()
        with path.open('rb') as stream:
            stream.seek(start);remaining=end-start+1
            while remaining>0:
                chunk=stream.read(min(65536,remaining))
                if not chunk:break
                try:self.wfile.write(chunk)
                except (BrokenPipeError,ConnectionResetError):break
                remaining-=len(chunk)

    def do_POST(self):
        if not self.local_host():
            return self.reply({'error': '로컬 주소로 접속하세요.'}, 403)
        # Only the local app may change local settings; reject cross-origin requests.
        if self.headers.get('Origin') not in (None, 'http://' + self.headers.get('Host', '')):
            return self.reply({'error': '외부 페이지의 요청은 허용하지 않습니다.'}, 403)
        if self.path in ('/api/updates/check', '/api/updates/open/release', '/api/updates/open/download'):
            try:
                result = updates.check()
                if self.path != '/api/updates/check':
                    url = result['downloadUrl'] if self.path.endswith('/download') else result['releaseUrl']
                    if not url or not result['available']:
                        raise ValueError('다운로드할 새 버전이 없습니다.')
                    open_external(url)
                    return self.reply({'ok': True})
                return self.reply(result)
            except Exception:
                return self.reply({'error': '업데이트 정보를 확인하거나 링크를 열지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.'}, 503)
        if self.path == '/api/setup':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024:raise ValueError('잘못된 요청 크기입니다.')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('잘못된 준비 요청입니다.')
                return self.reply(installer.start(body.get('component')),202)
            except (ValueError,RuntimeError) as error:
                return self.reply({'error':str(error)},400)
        if self.path == '/api/sponsor/paypal':
            try:
                open_paypal()
                return self.reply({'ok': True})
            except (OSError, subprocess.SubprocessError):
                return self.reply({'error': '기본 브라우저를 열지 못했습니다. 잠시 후 다시 시도해 주세요.'}, 500)
        if self.path == '/api/rename':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('잘못된 요청 크기입니다.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('잘못된 제목 수정 요청입니다.')
                return self.reply(engine.rename_result(body.get('id'), body.get('title')))
            except FileNotFoundError as e:
                return self.reply({'error': str(e)}, 404)
            except (ValueError, TypeError) as e:
                return self.reply({'error': str(e)}, 400)
            except OSError:
                return self.reply({'error': '제목을 저장할 수 없습니다. 다시 시도해 주세요.'}, 500)
        if self.path == '/api/delete':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024:
                    raise ValueError('잘못된 요청 크기입니다.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('잘못된 삭제 요청입니다.')
                engine.delete_result(body.get('id'))
                return self.reply({'ok': True})
            except FileNotFoundError as e:
                return self.reply({'error': str(e)}, 404)
            except (ValueError, TypeError) as e:
                return self.reply({'error': str(e)}, 400)
            except OSError:
                return self.reply({'error': '삭제할 수 없습니다. 파일 접근 권한을 확인하세요.'}, 500)
        if self.path == '/api/cancel':
            engine.cancel()
            return self.reply({'ok': True})
        if self.path == '/api/generate':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32768: raise ValueError('잘못된 요청 크기입니다.')
                body = json.loads(self.rfile.read(length))
                settings = validate(body['settings'])
                info = diagnose()
                settings = resolve_generation_settings(settings, info)
                return self.reply(engine.start(settings, body.get('prompt'), info['availableGB'], body.get('lyrics', ''), body.get('language', 'ko'), body.get('title', '')), 202)
            except (ValueError, TypeError, KeyError) as e:
                return self.reply({'error': str(e)}, 400)
        if self.path != '/api/settings':
            return self.reply({'error': '찾을 수 없습니다.'}, 404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('잘못된 요청 크기입니다.')
            settings = validate(json.loads(self.rfile.read(length)))
            with LOCK:
                DATA.mkdir(parents=True, exist_ok=True)
                tmp = DATA / 'settings.tmp'
                tmp.write_text(json.dumps(settings, ensure_ascii=False), encoding='utf-8')
                tmp.replace(DATA / 'settings.json')
            self.reply({'settings': settings})
        except (ValueError, TypeError, KeyError) as e:
            self.reply({'error': str(e)}, 400)
        except OSError:
            self.reply({'error': '설정을 저장할 수 없습니다.'}, 500)

if __name__ == '__main__':
    import signal
    from local_server import backend_session
    def stop(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:
        with backend_session(Handler,DATA,int(os.environ.get('PORT','8765'))) as session:
            print('소리숲: '+session.url,flush=True)
            try:
                if session.owned:threading.Event().wait()
                else:print('실행 중인 소리숲 서버를 사용합니다.',flush=True)
            finally:
                if session.owned:
                    installer.shutdown();engine.cancel()
                    deadline=time.monotonic()+5
                    while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.05)
    except KeyboardInterrupt:pass
