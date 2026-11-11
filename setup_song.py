"""Install the pinned ACE-Step runtime and only the required model components."""
import os
import platform
import re
import subprocess
import tomllib
from song_runtime import VERSIONS, ready as runtime_ready, detect_nvidia_gpu
from app_paths import ROOT, ENGINE_ROOT, uv_path, create_venv, background_options
from runtime_download import install_source

print('1/4 · 노래 엔진 파일을 확인하고 내려받습니다.', flush=True)
repo = ENGINE_ROOT / 'ace-step'
install_source('ace-step/ACE-Step-1.5', (ROOT / 'song-engine-version.txt').read_text(encoding='utf-8').strip(), repo)
python = repo / ('.venv/Scripts/python.exe' if platform.system() == 'Windows' else '.venv/bin/python')
print('2/4 · 노래 실행 환경과 필요한 프로그램을 설치합니다.', flush=True)
create_venv(repo / '.venv')

if platform.system() == 'Darwin':
    requirements = ROOT / 'requirements-song-mac.lock'
    subprocess.run([uv_path(), 'pip', 'install', '--python', str(python), '-r', str(requirements)], check=True, **background_options())
else:
    gpu = detect_nvidia_gpu()
    use_cuda = gpu is not None and gpu.get('vramGB', 0) >= 5.5
    installed_cuda = False
    if use_cuda:
        print(f"NVIDIA GPU 감지: {gpu['name']} ({gpu['vramGB']}GB VRAM)", flush=True)
        print("RTX 50 시리즈를 지원하는 CUDA 12.8 가속 패키지를 설치합니다…", flush=True)
        try:
            subprocess.run([uv_path(), 'pip', 'install', '--python', str(python),
                            'torch', 'torchvision', 'torchaudio',
                            '--upgrade',
                            '--reinstall-package', 'torch', '--reinstall-package', 'torchvision', '--reinstall-package', 'torchaudio',
                            '--index-url', 'https://download.pytorch.org/whl/cu128'],
                           check=True, **background_options())
            installed_cuda = True
        except Exception as error:
            raise RuntimeError("CUDA 패키지 설치에 실패했습니다. 인터넷 연결과 설치 로그를 확인하고 노래 엔진 준비를 다시 실행하세요. CPU로 자동 전환하지 않습니다.") from error

    if not installed_cuda:
        print("CPU 호환 모드 패키지를 설치합니다…", flush=True)
        subprocess.run([uv_path(), 'pip', 'install', '--python', str(python),
                        *[name + '==' + version for name, version in VERSIONS.items()],
                        '--reinstall-package', 'torch', '--reinstall-package', 'torchvision', '--reinstall-package', 'torchaudio',
                        '--index-url', 'https://download.pytorch.org/whl/cpu'],
                       check=True, **background_options())

    deps = tomllib.loads((repo / 'pyproject.toml').read_text(encoding='utf-8'))['project']['dependencies']
    excluded = {'torch', 'torchvision', 'torchaudio', 'mlx', 'mlx-lm', 'nano-vllm'}
    deps = [dep for dep in deps if re.split(r'[<>=;\[ ]', dep)[0] not in excluded]
    requirements = repo / ('sorisup-cuda-requirements.txt' if installed_cuda else 'sorisup-cpu-requirements.txt')
    requirements.write_text('\n'.join(deps) + '\n', encoding='utf-8')
    constraint = [] if installed_cuda else ['-c', str(ROOT / 'requirements-song-windows-cpu.lock')]
    subprocess.run([uv_path(), 'pip', 'install', '--python', str(python), '-r', str(requirements), *constraint], check=True, **background_options())

if platform.system() == 'Windows':
    print('노래 실행 패키지와 DLL 호환성을 검사합니다.', flush=True)
    report = repo / '.sorisup-song-runtime-check.json'
    try:
        subprocess.run([str(python), str(ROOT / 'song_runtime.py'), '--folder', str(repo), '--report', str(report), *(['--require-cuda'] if installed_cuda else [])], check=True, **background_options())
    except Exception as check_err:
        if installed_cuda:
            raise RuntimeError('GPU 실행 검사에 실패했습니다. NVIDIA 드라이버를 업데이트한 뒤 노래 엔진 준비를 다시 실행하세요. 설치 로그에서 CUDA 오류를 확인할 수 있습니다.') from check_err
        raise
    report.replace(repo / '.sorisup-song-runtime.json')
    if not runtime_ready(repo, 'cuda' if installed_cuda else 'cpu'): raise RuntimeError('노래 실행 패키지 검증 기록을 확인하지 못했습니다.')

if os.environ.get('LOCAL_MUSIC_SONG_RUNTIME_ONLY') == '1':
    print('노래 실행 패키지 검사 완료 · 모델 다운로드는 생략합니다.', flush=True)
    raise SystemExit(0)

env = {**os.environ, 'HF_HUB_DISABLE_XET': '1', 'HF_HUB_DISABLE_TELEMETRY': '1'}
print('3/4 · 노래 생성·보컬 모델 파일을 다운로드합니다.', flush=True)
revision = (ROOT / 'song-model-version.txt').read_text(encoding='utf-8').strip()
code = "from huggingface_hub import snapshot_download; snapshot_download('ACE-Step/Ace-Step1.5',local_dir=" + repr(str(repo / 'checkpoints')) + ",revision=" + repr(revision) + ",allow_patterns=['acestep-v15-turbo/*','vae/*','Qwen3-Embedding-0.6B/*'],max_workers=3)"
subprocess.run([str(python), '-c', code], env=env, check=True, **background_options())
print('4/4 · 노래 구성 모델 파일을 다운로드합니다.', flush=True)
planner_revision = (ROOT / 'song-planner-version.txt').read_text(encoding='utf-8').strip()
code = "from huggingface_hub import snapshot_download; snapshot_download('ACE-Step/acestep-5Hz-lm-0.6B',revision=" + repr(planner_revision) + ",local_dir=" + repr(str(repo / 'checkpoints/acestep-5Hz-lm-0.6B')) + ",max_workers=3)"
subprocess.run([str(python), '-c', code], env=env, check=True, **background_options())
print('노래 엔진과 모델 설치 완료')
