"""Install a pinned upstream runtime; model use remains subject to upstream terms."""
import platform
import subprocess
from app_paths import ROOT,ENGINE_ROOT,uv_path
from runtime_download import install_source

repo=ENGINE_ROOT/'stable-audio-3'
install_source('Stability-AI/stable-audio-3',(ROOT/'engines-version.txt').read_text(encoding='utf-8').strip(),repo,subdirs=['optimized/mlx','optimized/tflite'])
backend='mlx' if platform.system()=='Darwin' and platform.machine()=='arm64' else 'tflite'
folder=repo/'optimized'/backend
python=folder/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python')
if not python.exists():subprocess.run([uv_path(),'venv','--python','3.11',str(folder/'.venv')],check=True)
requirements=ROOT/'requirements-mlx.lock' if backend=='mlx' else folder/'requirements.txt'
subprocess.run([uv_path(),'pip','install','--python',str(python),'-r',str(requirements)],check=True)
print('실행 환경을 설치했습니다. 모델은 첫 생성 시 다운로드합니다.')
print('모델 약관: https://huggingface.co/stabilityai/stable-audio-3-small-music')
