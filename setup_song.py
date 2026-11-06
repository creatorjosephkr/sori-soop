"""Install the pinned ACE-Step runtime and only the required model components."""
import os
import platform
import re
import subprocess
import tomllib
from app_paths import ROOT,ENGINE_ROOT,uv_path,create_venv
from runtime_download import install_source

print('1/4 · 노래 엔진 파일을 확인하고 내려받습니다.',flush=True)
repo=ENGINE_ROOT/'ace-step'
install_source('ace-step/ACE-Step-1.5',(ROOT/'song-engine-version.txt').read_text(encoding='utf-8').strip(),repo)
python=repo/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python')
print('2/4 · 노래 실행 환경과 필요한 프로그램을 설치합니다.',flush=True)
create_venv(repo/'.venv')
if platform.system()=='Darwin':
    requirements=ROOT/'requirements-song-mac.lock'
else:
    # This release intentionally runs Windows through CPU, compatible with older GPUs.
    subprocess.run([uv_path(),'pip','install','--python',str(python),'torch','torchvision','torchaudio','--index-url','https://download.pytorch.org/whl/cpu'],check=True)
    deps=tomllib.loads((repo/'pyproject.toml').read_text(encoding='utf-8'))['project']['dependencies']
    excluded={'torch','torchvision','torchaudio','mlx','mlx-lm','nano-vllm'}
    deps=[dep for dep in deps if re.split(r'[<>=;\[ ]',dep)[0] not in excluded]
    requirements=repo/'sorisup-cpu-requirements.txt';requirements.write_text('\n'.join(deps)+'\n', encoding='utf-8')
subprocess.run([uv_path(),'pip','install','--python',str(python),'-r',str(requirements)],check=True)
env={**os.environ,'HF_HUB_DISABLE_XET':'1','HF_HUB_DISABLE_TELEMETRY':'1'}
print('3/4 · 노래 생성·보컬 모델 파일을 다운로드합니다.',flush=True)
revision=(ROOT/'song-model-version.txt').read_text(encoding='utf-8').strip()
code="from huggingface_hub import snapshot_download; snapshot_download('ACE-Step/Ace-Step1.5',local_dir="+repr(str(repo/'checkpoints'))+",revision="+repr(revision)+",allow_patterns=['acestep-v15-turbo/*','vae/*','Qwen3-Embedding-0.6B/*'],max_workers=3)"
subprocess.run([str(python),'-c',code],env=env,check=True)
print('4/4 · 노래 구성 모델 파일을 다운로드합니다.',flush=True)
planner_revision=(ROOT/'song-planner-version.txt').read_text(encoding='utf-8').strip()
code="from huggingface_hub import snapshot_download; snapshot_download('ACE-Step/acestep-5Hz-lm-0.6B',revision="+repr(planner_revision)+",local_dir="+repr(str(repo/'checkpoints/acestep-5Hz-lm-0.6B'))+",max_workers=3)"
subprocess.run([str(python),'-c',code],env=env,check=True)
print('노래 엔진과 모델 설치 완료')
