"""Offline regression check for first-run setup without managed-Python links."""
import base64
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from app_paths import ENGINE_ROOT,create_venv,uv_path,bootstrap_python

assert sys.platform=='win32'
assert bootstrap_python() and os.environ.get('UV_PYTHON_DOWNLOADS')=='never'
folder=ENGINE_ROOT/'bootstrap-check';folder.mkdir(parents=True,exist_ok=True)
create_venv(folder/'.venv')
python=folder/'.venv/Scripts/python.exe'
name='sorisoop_setup_probe';info=name+'-1.0.0.dist-info'
files={name+'/__init__.py':b'VALUE=42\n',info+'/METADATA':b'Metadata-Version: 2.1\nName: sorisoop-setup-probe\nVersion: 1.0.0\n',info+'/WHEEL':b'Wheel-Version: 1.0\nGenerator: SoriSoop check\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
record=''.join(path+',sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')+','+str(len(data))+'\n' for path,data in files.items())
files[info+'/RECORD']=(record+info+'/RECORD,,\n').encode()
wheel=folder/(name+'-1.0.0-py3-none-any.whl')
with zipfile.ZipFile(wheel,'w') as archive:
    for path,data in files.items():archive.writestr(path,data)
subprocess.run([uv_path(),'pip','install','--python',str(python),'--offline','--no-python-downloads','--no-managed-python',str(wheel)],check=True)
subprocess.run([str(python),'-c','import ssl,sqlite3,sorisoop_setup_probe;assert sorisoop_setup_probe.VALUE==42'],check=True)
# No junctions or symbolic links are needed anywhere in this environment.
assert all(not (path.lstat().st_file_attributes & 0x400) for path in (folder/'.venv').rglob('*'))
print('Windows first-run setup verified: bundled Python, copied venv, offline package install, no junctions.',flush=True)
