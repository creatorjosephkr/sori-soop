"""Install a small CPU-only Korean → English translator; inference is offline."""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from app_paths import ROOT, ENGINE_ROOT, uv_path, create_venv,background_options
FOLDER=ENGINE_ROOT/'translation'
MODEL_ID='Helsinki-NLP/opus-mt-ko-en'
REVISION=(ROOT/'translation-model-version.txt').read_text(encoding='utf-8').strip()

def main():
    print('1/4 · 한국어 번역 실행 환경을 준비합니다.',flush=True)
    FOLDER.mkdir(parents=True,exist_ok=True)
    python=FOLDER/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python')
    create_venv(FOLDER/'.venv')
    # CPU PyTorch is needed only for the one-time model conversion.
    args=[uv_path(),'pip','install','--python',str(python),'torch==2.12.1']
    if platform.system()!='Darwin':args+=['--index-url','https://download.pytorch.org/whl/cpu']
    print('2/4 · 번역에 필요한 프로그램을 설치합니다.',flush=True)
    subprocess.run(args,check=True,**background_options())
    subprocess.run([uv_path(),'pip','install','--python',str(python),'-r',str(ROOT/'requirements-translation.txt')],check=True,**background_options())
    env={**os.environ,'HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','HF_HUB_DISABLE_XET':'1'}
    source=FOLDER/'source';target=FOLDER/'model';pending=FOLDER/'model-installing'
    code="from huggingface_hub import snapshot_download; snapshot_download(repo_id="+repr(MODEL_ID)+",revision="+repr(REVISION)+",local_dir="+repr(str(source))+",allow_patterns=['*.json','*.spm','pytorch_model.bin','README.md'],max_workers=3)"
    print('3/4 · 한국어 번역 모델 파일을 내려받습니다.',flush=True)
    subprocess.run([str(python),'-c',code],env=env,check=True,**background_options())
    print('4/4 · 내 컴퓨터에서 사용할 번역 모델로 변환합니다. 시간이 걸릴 수 있습니다.',flush=True)
    shutil.rmtree(pending,ignore_errors=True)
    subprocess.run([str(python),'-c',"from ctranslate2.converters import TransformersConverter; TransformersConverter("+repr(str(source))+").convert("+repr(str(pending))+",quantization='int8')"],env={**env,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'},check=True,**background_options())
    for name in ('source.spm','target.spm','README.md'):shutil.copy2(source/name,pending/name)
    (pending/'source.json').write_text(json.dumps({'model':MODEL_ID,'revision':REVISION,'license':'Apache-2.0','quantization':'int8'},indent=2), encoding='utf-8')
    shutil.rmtree(target,ignore_errors=True);pending.replace(target)
    print('로컬 한영 번역 모델 설치 완료',flush=True)

if __name__=='__main__':main()
