"""ACE-Step adapter: direct lyric conditioning, one isolated process per song."""
import argparse
import json
import os
import sys
from pathlib import Path
if sys.platform=='win32':
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001|0x0002|0x8000)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app_paths import ENGINE_ROOT
REPO = ENGINE_ROOT / 'ace-step'
sys.path.insert(0, str(REPO))
from audio_processing import write_wav
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

p=argparse.ArgumentParser()
p.add_argument('--request',required=True)
p.add_argument('--out',required=True)
p.add_argument('--progress',required=True)
a=p.parse_args()
job=json.loads(Path(a.request).read_text(encoding='utf-8'))
caption=job.get('generationPrompt',job['prompt'])
progress=Path(a.progress)
def stage(text):
    temp=progress.with_suffix('.tmp')
    temp.write_text(json.dumps({'phase':text},ensure_ascii=False), encoding='utf-8')
    temp.replace(progress)
    print(text,flush=True)

stage('노래 엔진을 준비하고 있습니다')
import torch
import soundfile as sf
import numpy as np
from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

class LocalSongHandler(AceStepHandler):
    def _ensure_models_present(self, *, checkpoint_path, config_path, prefer_source, vae_variant=None):
        # The direct-conditioning pipeline needs no planning LM. Do not fetch the full bundle.
        required=['acestep-v15-turbo/model.safetensors','vae/diffusion_pytorch_model.safetensors','Qwen3-Embedding-0.6B/model.safetensors']
        if not all((checkpoint_path/x).is_file() for x in required):
            raise RuntimeError('노래 모델이 설치되지 않았습니다. setup_song.py를 실행하세요.')
        return None

    def _init_mlx_vae(self):
        if job['settings']['backend'] == 'cpu':
            return False
        return super()._init_mlx_vae()

    def _load_main_model_from_checkpoint(self, **kwargs):
        # Keep one BF16 MPS model, avoiding a second native MLX DiT copy.
        if self.device == 'mps':
            try:
                torch.empty((), dtype=torch.bfloat16, device='mps')
                self.dtype = torch.bfloat16
            except (TypeError, RuntimeError):
                self.dtype = torch.float32
        return super()._load_main_model_from_checkpoint(**kwargs)

settings=job['settings']
device='mps' if settings['backend']=='apple' else 'cpu'
stage('가사에 맞는 곡 구성을 준비하고 있습니다')
from acestep.llm_inference import LLMHandler
import gc, random
random.seed(job['seed']); np.random.seed(job['seed']); torch.manual_seed(job['seed'])
if device == 'mps':
    import mlx.core as mx
    mx.random.seed(job['seed'])
planner=LLMHandler()
message,ok=planner.initialize(checkpoint_dir=str(REPO/'checkpoints'),lm_model_path='acestep-5Hz-lm-0.6B',
    backend='mlx' if device=='mps' else 'pt',device=device,offload_to_cpu=False)
if not ok:
    raise RuntimeError(message)
try:
    plan=planner.generate_with_stop_condition(caption=caption,lyrics=job['lyrics'],
        infer_type='llm_dit',target_duration=settings['seconds'],
        user_metadata={'duration':settings['seconds']},use_cot_caption=False,
        use_cot_language=False,use_cot_metas=True,cfg_scale=1.0,
        batch_size=1,seeds=[job['seed']])
    if not plan.get('success') or not plan.get('audio_codes'):
        raise RuntimeError(plan.get('error') or '곡 구성을 생성하지 못했습니다.')
finally:
    planner.unload();del planner;gc.collect()
    if device=='mps':
        mx.clear_cache();torch.mps.empty_cache()
metadata=plan.get('metadata') or {}
plan_path=Path(a.progress.replace('.progress.json','.plan.json'))
plan_path.write_text(json.dumps({'metadata':metadata,'audioCodes':plan['audio_codes']},ensure_ascii=False), encoding='utf-8')
handler=LocalSongHandler()
stage('노래 모델을 메모리에 불러오고 있습니다')
message,ok=handler.initialize_service(project_root=str(REPO),config_path='acestep-v15-turbo',
    device=device,offload_to_cpu=True,offload_dit_to_cpu=True,
    compile_model=False,quantization=None,use_flash_attention=False,use_mlx_dit=False)
if not ok:
    raise RuntimeError(message)
stage('가사와 음악 설명으로 노래를 생성하고 있습니다')
params=GenerationParams(caption=caption,lyrics=job['lyrics'],instrumental=False,
    vocal_language=job['language'],duration=settings['seconds'],seed=job['seed'],
    audio_codes=plan['audio_codes'],bpm=metadata.get('bpm'),keyscale=metadata.get('keyscale',''),
    timesignature=str(metadata.get('timesignature','')),
    inference_steps=8,thinking=False,use_cot_metas=False,use_cot_caption=False,
    use_cot_language=False,enable_normalization=False)
config=GenerationConfig(batch_size=1,use_random_seed=False,seeds=[job['seed']],audio_format='wav')
output=Path(a.out)
result=generate_music(handler,None,params,config,save_dir=None)
if not result.success or not result.audios:
    raise RuntimeError(result.error or result.status_message or '노래 생성 실패')
stage('완성된 노래를 저장하고 있습니다')
first=result.audios[0]
audio=first['tensor'].detach().float().cpu().numpy().T
rate=first['sample_rate']
if not np.isfinite(audio).all() or not np.any(audio):
    raise RuntimeError('유효한 음악 신호가 생성되지 않았습니다.')
write_wav(output,audio,rate,settings.get('peakDb',-6),channels_first=False)
if sys.platform == 'win32':
    import psutil
    peak = psutil.Process().memory_info().peak_wset
else:
    import resource
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform!='darwin':peak*=1024
print(f'process peak RSS {peak/1024**3:.2f} GB',flush=True)
stage('노래 생성 완료')
