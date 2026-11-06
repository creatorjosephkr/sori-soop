"""Native desktop launcher; runtime files share the application drive."""
import argparse
import contextlib
import json
import os
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
from pathlib import Path


def configure(testing=False):
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    os.environ.setdefault('LOCAL_MUSIC_RESOURCES',str(root))
    if testing:
        os.environ['LOCAL_MUSIC_AUTO_SETUP']='0'
        os.environ['LOCAL_MUSIC_DATA']=tempfile.mkdtemp(prefix='sorisup-check-')
        os.environ['LOCAL_MUSIC_ENGINES']=str(Path(os.environ['LOCAL_MUSIC_DATA'])/'engines')
        os.environ['LOCAL_MUSIC_STORAGE']=os.environ['LOCAL_MUSIC_DATA']
    if getattr(sys,'frozen',False) or testing:
        from storage import configure_caches
        configure_caches()
    import certifi
    os.environ.setdefault('SSL_CERT_FILE',certifi.where())
    os.environ.setdefault('REQUESTS_CA_BUNDLE',certifi.where())
    os.environ.setdefault('PYTHONUTF8','1')
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1')
    os.environ.setdefault('DO_NOT_TRACK','1')
    from app_paths import DATA
    DATA.mkdir(parents=True,exist_ok=True)
    if getattr(sys,'frozen',False) and not testing:
        sys.stdout=(DATA/'desktop.log').open('a',encoding='utf-8',buffering=1)
        sys.stderr=sys.stdout
    if sys.stdout is None:sys.stdout=(DATA/'desktop.log').open('a',encoding='utf-8',buffering=1)
    if sys.stderr is None:sys.stderr=sys.stdout
    return root,DATA

@contextlib.contextmanager
def instance_lock(data):
    file=(data/'desktop.lock').open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            if file.seek(0,2)==0:file.write(b'0');file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        file.close();raise RuntimeError('소리숲이 이미 실행 중입니다. 열려 있는 소리숲 창을 확인해 주세요.')
    try:yield
    finally:file.close()

def notify_error(message):
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,str(message),'소리숲',0x10)
    elif sys.platform=='darwin':
        import subprocess
        # AppleScript string literals must be escaped, never interpolated as shell code.
        escaped=str(message).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')
        subprocess.run(['osascript','-e','display alert "소리숲" message "'+escaped+'" as critical'],check=False)

def run(args,root,data):
    import app,engine,installer
    from local_server import backend_session
    preferred=int(os.environ.get('PORT','8765'))
    # Test the real collision path too, rather than always hiding it with port 0.
    reserved=None
    if args.self_test or args.smoke_ui or args.bootstrap_test:
        import socket
        reserved=socket.socket();reserved.bind(('127.0.0.1',0));reserved.listen(1)
        preferred=reserved.getsockname()[1]
    session_context=backend_session(app.Handler,data,preferred)
    session=session_context.__enter__()
    url=session.url
    result={'ok':False}
    try:
        if args.self_test:
            from app_paths import uv_path,ENGINE_ROOT,background_options
            import subprocess
            for endpoint in ['/','/style.css','/app.js','/setup.js','/icons/sorisup.svg','/fonts/NotoSansKR-Variable.ttf','/spon/spon.svg']:
                with urllib.request.urlopen(url+endpoint) as response:assert response.status==200
            status=json.load(urllib.request.urlopen(url+'/api/setup'))
            assert not any(status['ready'].values())
            assert ENGINE_ROOT==data/'engines'
            subprocess.run([uv_path(),'--version'],check=True,**background_options())
            assert int(url.rsplit(':',1)[1])!=preferred
            result={'ok':True,'mode':'packaged-server','resources':True,'firstRunReady':True,'uv':True,'portCollisionHandled':int(url.rsplit(':',1)[1])!=preferred}
        elif args.bootstrap_test:
            installer.SCRIPTS['bootstrap-check']='setup_bootstrap_check.py'
            installer.run('bootstrap-check')
            result={'ok':True,'mode':'first-run-bootstrap','bundledPython':True,'copyBasedVenv':True,'offlinePackageInstall':True,'noManagedLinks':True,'noConsoleWindow':True}
        else:
            import webview
            webview.settings['ALLOW_DOWNLOADS']=True
            webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER']=True
            window=webview.create_window('소리숲',url,width=1440,height=1000,min_size=(960,700),hidden=args.smoke_ui,background_color='#f6f7f3',text_select=True)
            if args.smoke_ui:
                def check():
                    try:
                        for _ in range(120):
                            if window.evaluate_js("!!document.getElementById('prompt') && typeof state !== 'undefined' && !!state && !!document.getElementById('setup-retry') && !!document.getElementById('setup-steps')"):
                                result.update(ok=True,mode='native-webview',version=window.evaluate_js("document.querySelector('.app-version').textContent"),portCollisionHandled=int(url.rsplit(':',1)[1])!=preferred);break
                            time.sleep(.5)
                    except Exception as error:result.update(error=str(error))
                    finally:window.destroy()
                window.events.loaded+=lambda:threading.Thread(target=check,daemon=True).start()
            webview.start(private_mode=False,storage_path=str(data/'webview'),debug=False)
            if not args.smoke_ui:result.update(ok=True,mode='native-webview')
        return result
    finally:
        if session.owned:
            installer.shutdown();engine.cancel()
            deadline=time.monotonic()+5
            while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.05)
        session_context.__exit__(None,None,None)
        if reserved:reserved.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bootstrap-test',action='store_true');parser.add_argument('--self-test',action='store_true');parser.add_argument('--smoke-ui',action='store_true');parser.add_argument('--report')
    args=parser.parse_args();testing=args.self_test or args.smoke_ui or args.bootstrap_test
    root,data=configure(testing)
    try:
        with contextlib.nullcontext() if testing else instance_lock(data):result=run(args,root,data)
        if testing and not result['ok']:raise RuntimeError('앱 화면을 확인하지 못했습니다.')
        if args.report:Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2), encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as error:
        traceback.print_exc()
        if args.report:Path(args.report).write_text(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False), encoding='utf-8')
        if not testing:notify_error(str(error)+'\n\n진단 로그: '+str(data/'desktop.log'))
        return 1
    finally:
        if testing:
            import shutil
            shutil.rmtree(data,ignore_errors=True)

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
