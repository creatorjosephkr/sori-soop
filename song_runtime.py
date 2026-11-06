"""Lightweight readiness checks and isolated native validation for Windows songs."""
import json
from pathlib import Path

REVISION='windows-cpu-2.12.1-v1'
VERSIONS={'torch':'2.12.1+cpu','torchvision':'0.27.1+cpu','torchaudio':'2.11.1+cpu'}
MODEL_FILES=('acestep-v15-turbo/model.safetensors','vae/diffusion_pytorch_model.safetensors','Qwen3-Embedding-0.6B/model.safetensors','acestep-5Hz-lm-0.6B/model.safetensors')


def models_ready(folder):return all((Path(folder)/'checkpoints'/name).is_file() for name in MODEL_FILES)


def ready(folder):
    try:
        marker=json.loads((Path(folder)/'.sorisup-song-runtime.json').read_text(encoding='utf-8'))
        if marker.get('revision')!=REVISION or marker.get('versions')!=VERSIONS:return False
        site=Path(folder)/'.venv/Lib/site-packages'
        for name,expected in VERSIONS.items():
            metadata=site/(name+'-'+expected+'.dist-info')/'METADATA'
            if '\nVersion: '+expected+'\n' not in '\n'+metadata.read_text(encoding='utf-8'):return False
        return True
    except (OSError,ValueError,TypeError):return False


def validate_native(folder):
    import ctypes,sys
    ctypes.windll.kernel32.SetErrorMode(0x0001|0x0002|0x8000)
    from importlib.metadata import version
    actual={name:version(name) for name in VERSIONS}
    if actual!=VERSIONS:raise RuntimeError('노래 실행 패키지 버전이 맞지 않습니다: '+str(actual))
    import torch,torchvision,torchaudio
    assert torch.version.cuda is None,'CPU-only runtime required'
    result=torchvision.ops.nms(torch.tensor([[0.,0.,1.,1.]]),torch.tensor([1.]),.5)
    assert result.tolist()==[0],'torchvision native operations failed'
    sys.path.insert(0,str(folder))
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep.inference import GenerationParams
    assert AceStepHandler and LLMHandler and GenerationParams
    return {'ok':True,'revision':REVISION,'versions':actual,'nativeVisionOps':True,'aceStepImports':True}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
    result=validate_native(Path(args.folder));Path(args.report).write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result),flush=True)
