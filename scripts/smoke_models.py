"""Release-only CPU/MLX checks, never included in user generation history."""
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import engine,translation

def main():
    backend='apple' if platform.system()=='Darwin' and platform.machine()=='arm64' else 'cpu'
    with tempfile.TemporaryDirectory(prefix='sorisup-model-check-') as tmp:
        engine.DATA=Path(tmp)
        job=engine.start({'policy':'manual','mode':'bgm','model':'small-music','backend':backend,'seconds':10,'peakDb':-6},'차분한 피아노와 부드러운 드럼. 보컬 없는 배경음악.',8,title='release test')
        deadline=time.monotonic()+1200
        while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.25)
        assert not engine.ACTIVE,'Generation timed out'
        assert job['status']=='completed',job
        assert not translation.has_korean(job['generationPrompt']),job
        assert job['durationSeconds']==10,job
        assert job['outputPeakDb'] is None or job['outputPeakDb']<=-5.99,job
        print(json.dumps({'ok':True,'backend':backend,'captionTranslated':True,'seconds':job['durationSeconds'],'peakDb':job['outputPeakDb']}))

if __name__=='__main__':main()
