"""Lightweight readiness checks and isolated native validation for Windows songs."""
import json
import subprocess
from pathlib import Path

REVISION = 'windows-runtime-v3-cu128'
VERSIONS = {'torch': '2.12.1+cpu', 'torchvision': '0.27.1+cpu', 'torchaudio': '2.11.1+cpu'}
MODEL_FILES = ('acestep-v15-turbo/model.safetensors', 'vae/diffusion_pytorch_model.safetensors', 'Qwen3-Embedding-0.6B/model.safetensors', 'acestep-5Hz-lm-0.6B/model.safetensors')


def models_ready(folder):
    return all((Path(folder) / 'checkpoints' / name).is_file() for name in MODEL_FILES)


def detect_nvidia_gpu():
    """Detect NVIDIA GPU name, VRAM in GB, and driver version if present."""
    try:
        from app_paths import background_options
        opts = background_options()
    except ImportError:
        opts = {}
    try:
        raw = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'],
            timeout=5, stderr=subprocess.DEVNULL, text=True, **opts
        ).strip()
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                name = parts[0]
                vram_mb = float(parts[1])
                driver = parts[2] if len(parts) > 2 else ''
                return {'name': name, 'vramGB': round(vram_mb / 1024, 1), 'driver': driver}
    except Exception:
        pass
    return None


def ready(folder, backend=None):
    try:
        marker = json.loads((Path(folder) / '.sorisup-song-runtime.json').read_text(encoding='utf-8'))
        if marker.get('revision') not in (REVISION, 'windows-runtime-v2', 'windows-cpu-2.12.1-v1'):
            return False
        if not marker.get('ok', True):
            return False
        if backend == 'cuda' and (marker.get('revision') != REVISION or not marker.get('cuda') or marker.get('backend') != 'cuda'):
            return False
        site = Path(folder) / '.venv/Lib/site-packages'
        versions = marker.get('versions') or VERSIONS
        for name, expected in versions.items():
            metadata = site / (name + '-' + expected + '.dist-info') / 'METADATA'
            if '\nVersion: ' + expected + '\n' not in '\n' + metadata.read_text(encoding='utf-8'):
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False


def validate_native(folder, require_cuda=False):
    import ctypes, sys
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    from importlib.metadata import version
    actual = {name: version(name) for name in ('torch', 'torchvision', 'torchaudio')}
    import torch, torchvision, torchaudio
    cuda_available = torch.cuda.is_available()
    if require_cuda and not cuda_available:
        raise RuntimeError('CUDA를 사용할 수 없습니다. NVIDIA 드라이버와 GPU용 PyTorch 설치를 확인하세요.')
    backend_mode = 'cuda' if cuda_available else 'cpu'
    if cuda_available:
        gpu_name = torch.cuda.get_device_name(0)
        # Allocation alone does not prove this wheel contains usable GPU kernels.
        t = torch.ones((32, 32), device='cuda')
        result = t @ t
        torch.cuda.synchronize()
        assert result[0, 0].item() == 32, 'CUDA matrix operation failed'
        print(f'NVIDIA GPU 가속 확인: {gpu_name} (CUDA {torch.version.cuda})', flush=True)
    result = torchvision.ops.nms(torch.tensor([[0., 0., 1., 1.]]), torch.tensor([1.]), .5)
    assert result.tolist() == [0], 'torchvision native operations failed'
    if not cuda_available:
        print('CPU 모드 확인 완료', flush=True)
    sys.path.insert(0, str(folder))
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams
    assert AceStepHandler and LLMHandler and GenerationParams
    return {
        'ok': True,
        'revision': REVISION,
        'backend': backend_mode,
        'versions': actual,
        'cuda': cuda_available,
        'gpuName': torch.cuda.get_device_name(0) if cuda_available else None,
        'nativeVisionOps': True,
        'aceStepImports': True
    }


PLANNERS = {'light': 'acestep-5Hz-lm-0.6B', 'quality': 'acestep-5Hz-lm-1.7B'}


def planner_ready(folder, quality='light'):
    name = PLANNERS.get(quality)
    if not name:
        return False
    path = Path(folder) / 'checkpoints' / name
    return all((path / file).is_file() for file in ('model.safetensors', 'config.json', 'tokenizer.json', 'tokenizer_config.json'))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--require-cuda', action='store_true')
    args = parser.parse_args()
    result = validate_native(Path(args.folder), require_cuda=args.require_cuda)
    Path(args.report).write_text(json.dumps(result), encoding='utf-8')
    print(json.dumps(result), flush=True)
