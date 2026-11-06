"""Exercise installed launchers with small protocol probes, without loading AI models."""
import json
from pathlib import Path
import shutil
import time
from app_paths import bootstrap_python


GENERATOR='''import argparse,ctypes,json,wave
from pathlib import Path
assert ctypes.windll.kernel32.GetConsoleWindow()==0,'Generation launcher opened a console'
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seconds',type=int);p.add_argument('--request');a,_=p.parse_known_args()
seconds=json.loads(Path(a.request).read_text(encoding='utf-8'))['settings']['seconds'] if a.request else a.seconds
with wave.open(a.out,'wb') as stream:
 stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(bytes(seconds*8000*4))
'''
TRANSLATOR='''import argparse,ctypes,json
from pathlib import Path
assert ctypes.windll.kernel32.GetConsoleWindow()==0,'Translation launcher opened a console'
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--request');a=p.parse_args()
Path(a.out).write_text(json.dumps({'text':'Warm piano music','model':'console-check','revision':'test'}),encoding='utf-8')
'''


def check(data):
    import engine
    python=Path(bootstrap_python());root=Path(data)/'console-check';root.mkdir()
    script=root/'generate.py';script.write_text(GENERATOR,encoding='utf-8')
    (root/'runners').mkdir();(root/'runners/translate.py').write_text(TRANSLATOR,encoding='utf-8')
    for name in ('engines-version.txt','song-engine-version.txt','song-planner-version.txt'):
        shutil.copy2(engine.ROOT/name,root/name)
    replacements=[(engine,'ROOT',root),(engine,'ready',lambda *args:True),
                  (engine,'engine_paths',lambda *args:(root,python,script)),
                  (engine,'song_paths',lambda:(root,python,script)),
                  (engine.translation,'ready',lambda:True),
                  (engine.translation,'runtime_paths',lambda:(python,root))]
    previous=[(obj,key,getattr(obj,key)) for obj,key,value in replacements]
    try:
        for obj,key,value in replacements:setattr(obj,key,value)
        for mode,model in (('bgm','small-music'),('song','ace-step')):
            job=engine.start({'mode':mode,'model':model,'backend':'cpu','seconds':10,'peakDb':-6},'따뜻한 피아노',32,lyrics='[Verse]\nA new song',language='en')
            deadline=time.monotonic()+30
            while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.05)
            assert not engine.ACTIVE,'Console probe timed out'
            if job['status']!='completed':
                logs='\n'.join(path.read_text(encoding='utf-8',errors='replace') for path in Path(data).glob('jobs/'+job['id']+'*.log'))
                raise RuntimeError(str(job.get('error'))+'\n'+logs)
            assert job['translation']['model']=='console-check'
        return {'ok':True,'bgmLauncher':True,'songLauncher':True,'translationLauncher':True,'noConsoleWindow':True}
    finally:
        engine.cancel()
        deadline=time.monotonic()+5
        while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.05)
        for obj,key,value in previous:setattr(obj,key,value)
