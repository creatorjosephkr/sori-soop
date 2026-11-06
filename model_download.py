"""Download public BGM weights over HTTPS with visible byte progress and an idle limit."""
import argparse
import importlib.util
import logging
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import uuid


class DownloadWatchdog:
    def __init__(self, on_stall, idle_seconds=180):
        self.on_stall=on_stall;self.idle_seconds=idle_seconds
        self.last=time.monotonic();self.stop=threading.Event()
    def touch(self):self.last=time.monotonic()
    def __enter__(self):
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start();return self
    def run(self):
        while not self.stop.wait(min(1,self.idle_seconds/2)):
            if time.monotonic()-self.last>=self.idle_seconds:
                self.on_stall();return
    def __exit__(self,*args):self.stop.set();self.thread.join(timeout=2)


def materialize(source,target):
    source=Path(source);target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    pending=target.with_name(target.name+'.'+uuid.uuid4().hex+'.pending')
    try:
        try:pending.symlink_to(source)
        except OSError:
            try:os.link(source,pending)
            except OSError:shutil.copy2(source,pending)
        pending.replace(target)
    finally:
        if pending.exists() or pending.is_symlink():pending.unlink()


class AnonymousNotice(logging.Filter):
    def filter(self,record):
        if 'You are sending unauthenticated requests' in record.getMessage():
            record.msg='로그인 없이 공개 모델을 다운로드합니다. 서버 상황에 따라 속도가 제한될 수 있습니다.'
            record.args=()
        return True


def download_weights(folder,files):
    # These must be configured before huggingface_hub is imported.
    os.environ['HF_HUB_DISABLE_XET']='1'
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','30')
    os.environ.setdefault('HF_HUB_ETAG_TIMEOUT','15')
    from huggingface_hub import hf_hub_download
    from tqdm import tqdm
    spec=importlib.util.spec_from_file_location('studio_weights',Path(folder)/'scripts'/'weights.py')
    weights=importlib.util.module_from_spec(spec);spec.loader.exec_module(weights)
    for name in ('huggingface_hub.utils._http','huggingface_hub.file_download'):
        logging.getLogger(name).addFilter(AnonymousNotice())
    print('공개 모델을 일반 HTTPS 방식으로 다운로드합니다. 토큰 입력은 필요하지 않습니다.',flush=True)
    for relative in files:
        target=Path(folder)/relative
        if relative not in weights.FLAT_MANIFEST:raise ValueError('알 수 없는 모델 파일입니다.')
        if target.is_file() and target.stat().st_size>0:
            print('이미 준비됨: '+target.name,flush=True);continue
        def stalled():
            print('다운로드가 3분 동안 진행되지 않아 중단했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.',flush=True)
            # Only this dedicated download worker exits; OS releases its cache file lock.
            os._exit(75)
        with DownloadWatchdog(stalled) as watchdog:
            class Progress(tqdm):
                def __init__(self,*args,**kwargs):
                    self.last_print=0;self.last_bytes=-1
                    kwargs.update(disable=False,mininterval=1,miniters=1)
                    super().__init__(*args,**kwargs)
                def display(self,msg=None,pos=None):
                    now=time.monotonic()
                    if self.n!=self.last_bytes:watchdog.touch();self.last_bytes=self.n
                    if now-self.last_print<2 and self.n!=self.total:return
                    self.last_print=now
                    downloaded=self.n/1024**2
                    total=f' / {self.total/1024**2:.1f}MB ({min(100,self.n/self.total*100):.1f}%)' if self.total else 'MB'
                    print(f'{target.name}: {downloaded:.1f}'+total,flush=True)
            print('다운로드 시작: '+target.name,flush=True)
            source=hf_hub_download(repo_id=weights.REPO_ID,filename=weights.FLAT_MANIFEST[relative],tqdm_class=Progress)
        print('다운로드 완료, 파일을 배치합니다: '+target.name,flush=True)
        materialize(source,target)
        print('파일 준비 완료: '+target.name,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);parser.add_argument('files',nargs='+');args=parser.parse_args()
    download_weights(args.folder,args.files)

if __name__=='__main__':main()
