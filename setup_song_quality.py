"""Download the optional quality planner, keeping the lightweight default intact."""
import os
import platform
import subprocess
from app_paths import ROOT,ENGINE_ROOT,background_options
from song_runtime import planner_ready

repo=ENGINE_ROOT/'ace-step'
python=repo/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python')
if not python.exists():raise RuntimeError('노래 기본 실행 준비를 먼저 완료해 주세요.')
if planner_ready(repo,'quality'):
    print('품질 우선 1.7B 모델이 이미 준비되어 있습니다.',flush=True)
    raise SystemExit(0)
revision=(ROOT/'song-model-version.txt').read_text(encoding='utf-8').strip()
print('품질 우선 1.7B 모델을 준비합니다. 추가 다운로드 약 3.7GB입니다.',flush=True)
code="from huggingface_hub import snapshot_download; snapshot_download('ACE-Step/Ace-Step1.5',revision="+repr(revision)+",local_dir="+repr(str(repo/'checkpoints'))+",allow_patterns=['acestep-5Hz-lm-1.7B/*'],max_workers=3)"
subprocess.run([str(python),'-u','-c',code],check=True,env={**os.environ,'HF_HUB_DISABLE_XET':'1','HF_HUB_DISABLE_TELEMETRY':'1'},**background_options())
if not planner_ready(repo,'quality'):raise RuntimeError('품질 모델 파일을 확인하지 못했습니다. 다시 준비해 주세요.')
print('품질 우선 1.7B 모델 준비 완료',flush=True)
