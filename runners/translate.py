"""Offline INT8 CPU translation in a short-lived process, before music inference."""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from translation import runtime_paths,translate_segments,token_chunks,MODEL_ID,REVISION


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--request',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args()
    import ctranslate2
    import sentencepiece as spm
    _,model=runtime_paths()
    source=spm.SentencePieceProcessor(model_file=str(model/'source.spm'))
    target=spm.SentencePieceProcessor(model_file=str(model/'target.spm'))
    translator=ctranslate2.Translator(str(model),device='cpu',compute_type='int8',inter_threads=1,intra_threads=2)
    def translate(text):
        tokens=source.encode(text,out_type=str)
        chunks=token_chunks(tokens)
        results=translator.translate_batch(chunks,beam_size=4,max_batch_size=1,max_input_length=0,max_decoding_length=512,repetition_penalty=1.1)
        texts=[]
        for result in results:
            output=result.hypotheses[0]
            if len(output)>=511:raise ValueError('번역 결과가 너무 깁니다. 음악 설명을 줄여 주세요.')
            texts.append(target.decode(output))
        return ' '.join(texts)
    job=json.loads(Path(args.request).read_text(encoding='utf-8'))
    english=translate_segments(job.get('generationInputPrompt',job['prompt']),translate)
    result={'text':english,'model':MODEL_ID,'revision':REVISION}
    output=Path(args.out);pending=output.with_suffix('.tmp')
    pending.write_text(json.dumps(result,ensure_ascii=False), encoding='utf-8');pending.replace(output)
    print('로컬 한영 번역 완료',flush=True)

if __name__=='__main__':main()
