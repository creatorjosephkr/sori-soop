"""One backend per data folder, with safe reuse and automatic localhost ports."""
import contextlib
import errno
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path


class AlreadyLocked(RuntimeError):
    pass

@contextlib.contextmanager
def exclusive_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    file=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            if file.seek(0,2)==0:file.write(b'0');file.flush()
            file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError as error:
        file.close();raise AlreadyLocked('Already running') from error
    try:yield
    finally:file.close()

@dataclass
class Session:
    url: str
    owned: bool
    server: object=None

def read_record(path):
    try:
        record=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(record,dict) and type(record.get('port')) is int and 1<=record['port']<=65535:return record
    except (OSError,ValueError):pass
    return None

def connect_existing(path):
    # Never trust an arbitrary URL from disk: connections stay on 127.0.0.1.
    for _ in range(20):
        record=read_record(path)
        if record and isinstance(record.get('sessionId'),str):
            url='http://127.0.0.1:'+str(record['port'])
            try:
                with urllib.request.urlopen(url+'/api/session',timeout=.3) as response:
                    identity=json.load(response)
                if isinstance(identity,dict) and identity.get('app')=='sori-soop' and identity.get('sessionId')==record['sessionId']:
                    return Session(url,False)
            except (OSError,ValueError):pass
        time.sleep(.05)
    raise RuntimeError('실행 중인 소리숲 서버에 연결하지 못했습니다. 잠시 후 앱을 다시 실행해 주세요.')

class LocalHTTPServer(ThreadingHTTPServer):
    allow_reuse_address=os.name!='nt'
    def server_bind(self):
        if os.name=='nt':self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        return super().server_bind()

def bind_server(handler,preferred_port):
    try:return LocalHTTPServer(('127.0.0.1',preferred_port),handler)
    except OSError as error:
        if error.errno not in (errno.EADDRINUSE,10048,10013) and getattr(error,'winerror',None) not in (10048,10013):raise
        return LocalHTTPServer(('127.0.0.1',0),handler)

@contextlib.contextmanager
def backend_session(handler,data,preferred_port=8765):
    """Reuse only an identified backend whose data-folder lock is still held."""
    data=Path(data);data.mkdir(parents=True,exist_ok=True)
    record_path=data/'backend.json'
    lock=exclusive_lock(data/'backend.lock')
    try:lock.__enter__()
    except AlreadyLocked:
        yield connect_existing(record_path);return
    try:
        previous=read_record(record_path)
        # Keeping the last selected port also preserves browser-local preferences.
        port=previous['port'] if previous and preferred_port else preferred_port
        server=bind_server(handler,port)
        identity={'app':'sori-soop','sessionId':secrets.token_hex(16)}
        server.studio_session=identity
        pending=record_path.with_suffix('.tmp')
        pending.write_text(json.dumps({**identity,'port':server.server_port}),encoding='utf-8');pending.replace(record_path)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield Session('http://127.0.0.1:'+str(server.server_port),True,server)
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
    finally:lock.__exit__(None,None,None)
