"""Install a small CPU-only Korean → English translator; inference is offline."""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from app_paths import ROOT, ENGINE_ROOT, uv_path
FOLDER=ENGINE_ROOT/'translation'
MODEL_ID='Helsinki-NLP/opus-mt-ko-en'
REVISION=(ROOT/'translation-model-version.txt').read_text(encoding='utf-8').strip()

def main():
    FOLDER.mkdir(parents=True,exist_ok=True)
    python=FOLDER/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python')
    if not python.exists():subprocess.run([uv_path(),'venv','--python','3.11',str(FOLDER/'.venv')],check=True)
    # CPU PyTorch is needed only for the one-time model conversion.
    args=[uv_path(),'pip','install','--python',str(python),'torch==2.12.1']
    if platform.system()!='Darwin':args+=['--index-url','https://download.pytorch.org/whl/cpu']
    subprocess.run(args,check=True)
    subprocess.run([uv_path(),'pip','install','--python',str(python),'-r',str(ROOT/'requirements-translation.txt')],check=True)
    env={**os.environ,'HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','HF_HUB_DISABLE_XET':'1'}
    source=FOLDER/'source';target=FOLDER/'model';pending=FOLDER/'model-installing'
    code="from huggingface_hub import snapshot_download; snapshot_download(repo_id="+repr(MODEL_ID)+",revision="+repr(REVISION)+",local_dir="+repr(str(source))+",allow_patterns=['*.json','*.spm','pytorch_model.bin','README.md'],max_workers=3)"
    subprocess.run([str(python),'-c',code],env=env,check=True)
    shutil.rmtree(pending,ignore_errors=True)
    subprocess.run([str(python),'-c',"from ctranslate2.converters import TransformersConverter; TransformersConverter("+repr(str(source))+").convert("+repr(str(pending))+",quantization='int8')"],env={**env,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'},check=True)
    for name in ('source.spm','target.spm','README.md'):shutil.copy2(source/name,pending/name)
    (pending/'source.json').write_text(json.dumps({'model':MODEL_ID,'revision':REVISION,'license':'Apache-2.0','quantization':'int8'},indent=2), encoding='utf-8')
    shutil.rmtree(target,ignore_errors=True);pending.replace(target)
    print('로컬 한영 번역 모델 설치 완료',flush=True)

if __name__=='__main__':main()
