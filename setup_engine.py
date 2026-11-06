"""Install a pinned upstream runtime; model use remains subject to upstream terms."""
import platform
import os
import time
import subprocess
from app_paths import ROOT,ENGINE_ROOT,uv_path
from runtime_download import install_source

print('1/4 · 배경음악 엔진 파일을 확인하고 내려받습니다.',flush=True)
repo=ENGINE_ROOT/'stable-audio-3'
install_source('Stability-AI/stable-audio-3',(ROOT/'engines-version.txt').read_text(encoding='utf-8').strip(),repo,subdirs=['optimized/mlx','optimized/tflite'])
backend='mlx' if platform.system()=='Darwin' and platform.machine()=='arm64' else 'tflite'
folder=repo/'optimized'/backend
python=folder/('.venv/Scripts/python.exe' if platform.system()=='Windows' else '.venv/bin/python')
print('2/4 · 배경음악 Python 실행 환경을 준비합니다.',flush=True)
if not python.exists():subprocess.run([uv_path(),'venv','--python','3.11',str(folder/'.venv')],check=True)
requirements=ROOT/'requirements-mlx.lock' if backend=='mlx' else folder/'requirements.txt'
print('3/4 · 배경음악에 필요한 프로그램을 설치합니다.',flush=True)
subprocess.run([uv_path(),'pip','install','--python',str(python),'-r',str(requirements)],check=True)
print('4/4 · 배경음악 모델 파일을 다운로드합니다.',flush=True)
# Download only the small-music generation weights, without loading models into RAM.
files=(['models/mlx/t5gemma_f16.npz','models/mlx/dit_sm-music_f16.npz','models/mlx/same_s_decoder_f32.npz'] if backend=='mlx'
       else ['models/tflite/t5gemma/encoder_fp16.tflite','models/tflite/sa3-sm-music/dit_w8a8.tflite','models/tflite/same-s/dec_w8a8.tflite'])
env={**os.environ,'HF_HUB_DISABLE_XET':'1','HF_HUB_DOWNLOAD_TIMEOUT':'30','HF_HUB_ETAG_TIMEOUT':'15','PYTHONUNBUFFERED':'1'}
for attempt in range(1,4):
    result=subprocess.run([str(python),str(ROOT/'model_download.py'),'--folder',str(folder),*files],env=env)
    if result.returncode==0:break
    if attempt==3:raise RuntimeError('모델 다운로드를 완료하지 못했습니다. 인터넷 연결을 확인한 뒤 준비를 다시 시도해 주세요.')
    print(f'연결을 다시 시도합니다 ({attempt}/3). 완료된 파일은 유지합니다.',flush=True)
    time.sleep(3)
print('배경음악 실행 환경과 모델 준비를 마쳤습니다.')
print('모델 약관: https://huggingface.co/stabilityai/stable-audio-3-small-music')
