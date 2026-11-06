"""ACE-Step adapter: direct lyric conditioning, one isolated process per song."""
import argparse
import faulthandler
faulthandler.enable()
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
from song_duration import automatic,plan_options,planned_seconds
from song_lyrics import check_lyric_tokens,check_audio_codes,check_caption_tokens
REPO = ENGINE_ROOT / 'ace-step'
sys.path.insert(0, str(REPO))
from audio_processing import write_wav
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')

p=argparse.ArgumentParser()
p.add_argument('--phase',choices=('all','plan','render'),default='all')
p.add_argument('--request',required=True)
p.add_argument('--out',required=True)
p.add_argument('--progress',required=True)
a=p.parse_args()
job=json.loads(Path(a.request).read_text(encoding='utf-8'))
caption=job.get('generationPrompt',job['prompt'])
lyrics=job['lyrics']
progress=Path(a.progress)
def stage(text):
    temp=progress.with_suffix('.tmp')
    temp.write_text(json.dumps({'phase':text},ensure_ascii=False), encoding='utf-8')
    temp.replace(progress)
    print(text,flush=True)
    # Record memory at model boundaries, including before a native loader crash.
    try:
        import psutil
        process=psutil.Process().memory_info();memory=psutil.virtual_memory()
        print(f'[memory] process RSS={process.rss/1024**3:.2f} GB; available RAM={memory.available/1024**3:.2f} GB; total RAM={memory.total/1024**3:.2f} GB',flush=True)
    except (ImportError,OSError):pass

stage('노래 엔진을 준비하고 있습니다')
import torch
import soundfile as sf
import numpy as np
settings=job['settings']
device='mps' if settings['backend']=='apple' else 'cpu'
import gc, random
random.seed(job['seed']); np.random.seed(job['seed']); torch.manual_seed(job['seed'])
if device == 'mps':
    import mlx.core as mx
    mx.random.seed(job['seed'])
plan_path=Path(a.progress.replace('.progress.json','.plan.json'))
input_check_path=Path(a.progress.replace('.progress.json','.input-check.json'))
def validate_caption(tokenizer, text, *, formatted=True):
    try:
        count=check_caption_tokens(tokenizer,text,formatted=formatted)
    except ValueError as error:
        input_check_path.write_text(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False),encoding='utf-8')
        raise
    input_check_path.write_text(json.dumps({'ok':True,'tokens':count,'limit':256,'includesTemplate':formatted}),encoding='utf-8')
    print(f'음악 설명 확인: {count}/256 tokens'+(' (내부 지시문 포함)' if formatted else ' (설명 자체)'),flush=True)
    return count

def validate_planned_caption(metadata, duration):
    # Reuse pinned upstream formatters; the metadata is exactly what batch_prep builds.
    from transformers import AutoTokenizer
    from acestep.core.generation.handler.prompt_utils import PromptMixin
    from acestep.core.generation.handler.metadata_utils import MetadataMixin
    class InputFormatter(PromptMixin,MetadataMixin):pass
    formatter=InputFormatter()
    metas=formatter._build_metadata_dict(metadata.get('bpm'),metadata.get('keyscale',''),str(metadata.get('timesignature','')),duration)
    pure_caption=formatter.extract_caption_from_sft_format(caption)
    text,_=formatter.build_dit_inputs('text2music',None,pure_caption,lyrics,metas,job['language'])
    tokenizer=AutoTokenizer.from_pretrained(str(REPO/'checkpoints/Qwen3-Embedding-0.6B'),local_files_only=True)
    return validate_caption(tokenizer,text)

if a.phase!='render':
    stage('가사에 맞는 곡 구성과 길이를 정하고 있습니다' if automatic(settings) else '가사에 맞는 곡 구성을 준비하고 있습니다')
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(str(REPO/'checkpoints/Qwen3-Embedding-0.6B'),local_files_only=True)
    from acestep.core.generation.handler.prompt_utils import PromptMixin
    validate_caption(tokenizer,PromptMixin().extract_caption_from_sft_format(caption),formatted=False)
    token_count=check_lyric_tokens(tokenizer,lyrics,job['language'])
    print(f'전체 가사 확인: {token_count}/2048 tokens',flush=True)
    del tokenizer
    from acestep.llm_inference import LLMHandler
    planner=LLMHandler()
    message,ok=planner.initialize(checkpoint_dir=str(REPO/'checkpoints'),lm_model_path='acestep-5Hz-lm-0.6B',
        backend='mlx' if device=='mps' else 'pt',device=device,offload_to_cpu=False)
    if not ok:
        raise RuntimeError(message)
    try:
        plan=planner.generate_with_stop_condition(caption=caption,lyrics=lyrics,
            infer_type='llm_dit',**plan_options(settings),use_cot_caption=False,
            use_cot_language=False,use_cot_metas=True,cfg_scale=1.0,
            batch_size=1,seeds=[job['seed']])
        if not plan.get('success') or not plan.get('audio_codes'):
            raise RuntimeError(plan.get('error') or '곡 구성을 생성하지 못했습니다.')
    finally:
        planner.unload();del planner;gc.collect()
        if device=='mps':
            mx.clear_cache();torch.mps.empty_cache()
    metadata=plan.get('metadata') or {}
    duration=planned_seconds(settings,metadata,plan['audio_codes'])
    validate_planned_caption(metadata,duration)
    check_audio_codes(plan['audio_codes'],duration)
    if automatic(settings):stage(f'가사에 맞춰 정한 노래 길이: {duration}초')
    plan_path.write_text(json.dumps({'metadata':metadata,'audioCodes':plan['audio_codes'],'plannedSeconds':duration,'durationMode':settings.get('durationMode','manual')},ensure_ascii=False), encoding='utf-8')
    if a.phase=='plan':
        stage('곡 구성 완료 · 분석 프로세스의 메모리를 반환합니다')
        raise SystemExit(0)
else:
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    plan['audio_codes']=plan['audioCodes']
    metadata=plan.get('metadata') or {}
    duration=planned_seconds(settings,metadata,plan['audio_codes'])
    validate_planned_caption(metadata,duration)
    check_audio_codes(plan['audio_codes'],duration)

from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

class LocalSongHandler(AceStepHandler):
    def _prepare_text_conditioning_inputs(self, *args, **kwargs):
        original=self.text_tokenizer
        class CheckedTokenizer:
            def __getattr__(self,name):return getattr(original,name)
            def __call__(self,text,*token_args,**token_kwargs):
                if token_kwargs.get('max_length')==256:
                    validate_caption(original,text)
                return original(text,*token_args,**token_kwargs)
        self.text_tokenizer=CheckedTokenizer()
        try:return super()._prepare_text_conditioning_inputs(*args,**kwargs)
        finally:self.text_tokenizer=original

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

handler=LocalSongHandler()
stage('노래 모델을 메모리에 불러오고 있습니다')
message,ok=handler.initialize_service(project_root=str(REPO),config_path='acestep-v15-turbo',
    device=device,offload_to_cpu=True,offload_dit_to_cpu=True,
    compile_model=False,quantization=None,use_flash_attention=False,use_mlx_dit=False)
if not ok:
    raise RuntimeError(message)
stage('가사와 음악 설명으로 노래를 생성하고 있습니다')
params=GenerationParams(caption=caption,lyrics=lyrics,instrumental=False,
    vocal_language=job['language'],duration=duration,seed=job['seed'],
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
