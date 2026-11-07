"""Use upstream generation but replace its clipping PCM writer before saving."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from audio_processing import write_wav, validate_peak_db

parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--script',required=True)
parser.add_argument('--peak-db',type=float,default=-8)
args,remaining=parser.parse_known_args()
validate_peak_db(args.peak_db)
script=Path(args.script)
sys.path.insert(0,str(script.parent))
spec=importlib.util.spec_from_file_location('local_bgm_upstream',script)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
# The Windows upstream opens cmd.exe merely to enable terminal colors.
# There is no terminal to configure in the desktop application.
original_system=os.system
if sys.platform=='win32':
    os.system=lambda command:0 if command=='' else original_system(command)
try:
    spec.loader.exec_module(module)
finally:
    os.system=original_system
def save_wav(path,audio,sample_rate=44100):
    write_wav(path,audio,sample_rate,args.peak_db,channels_first=True)
if script.name=='sa3_tflite.py':
    module.P.save_wav=save_wav
else:
    module.save_wav=save_wav
sys.argv=[str(script),*remaining]
module.main()
