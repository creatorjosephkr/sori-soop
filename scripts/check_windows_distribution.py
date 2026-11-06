"""Exercise the real installer, installed app, shortcuts, and safe uninstall on Windows."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parent.parent


def run(command,timeout=600):
    result=subprocess.run(list(map(str,command)),timeout=timeout)
    if result.returncode not in (0,3010):raise RuntimeError(f'Windows installation check failed: {result.returncode}')


def main():
    version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
    artifacts=ROOT/'artifacts';installer=artifacts/f'SoriSoop-{version}-windows-x64-setup.exe'
    testroot=Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()))/('소리숲 설치 검증 '+uuid.uuid4().hex)
    target=testroot/'SoriSoop';app=target/'SoriSoop.exe'
    # Force both signed prerequisite installers to run even on prepared build hosts.
    run([installer,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/FORCEPREREQUISITES=1','/TASKS=desktopicon',f'/DIR={target}',f'/LOG={artifacts/"windows-install.log"}'])
    try:
        assert app.is_file()
        shell=subprocess.check_output(['pwsh','-NoProfile','-Command',"@{Desktop=[Environment]::GetFolderPath('Desktop');Programs=[Environment]::GetFolderPath('Programs')} | ConvertTo-Json"],text=True,encoding='utf-8-sig')
        folders=json.loads(shell)
        shortcuts=[Path(folders[key])/'소리숲.lnk' for key in ('Desktop','Programs')]
        assert all(path.is_file() for path in shortcuts),'Missing installed shortcuts'
        for flag,name in [('--self-test','windows-server.json'),('--smoke-ui','windows-window.json')]:
            report=artifacts/name;run([app,flag,'--report',report],timeout=120)
            assert json.loads(report.read_text(encoding='utf-8'))['ok']
        # An unusable uv managed-Python store must not block first-run setup.
        blocked=testroot/'blocked-python-store';blocked.write_text('not a directory',encoding='utf-8')
        env={**os.environ,'UV_PYTHON_INSTALL_DIR':str(blocked),'UV_PYTHON_DOWNLOADS':'never'}
        report=artifacts/'windows-bootstrap.json'
        subprocess.run([str(app),'--bootstrap-test','--report',str(report)],env=env,check=True,timeout=120)
        assert json.loads(report.read_text(encoding='utf-8'))['noManagedLinks']
        marker=target/'SoriSoop Data'/'keep-existing-model.txt';marker.parent.mkdir(exist_ok=True);marker.write_text('preserve',encoding='utf-8')
        run([target/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={artifacts/"windows-uninstall.log"}'])
        deadline=time.monotonic()+30
        while app.exists() and time.monotonic()<deadline:time.sleep(.2)
        assert not app.exists(),'App was not uninstalled'
        assert marker.read_text(encoding='utf-8')=='preserve','User model data was removed'
        assert all(not path.exists() for path in shortcuts),'Shortcut was not uninstalled'
        (artifacts/'windows-installer.json').write_text(json.dumps({'ok':True,'version':version,'prerequisiteInstallers':True,'installedApp':True,'shortcuts':True,'uninstall':True,'modelDataPreserved':True,'pathWithSpacesAndKorean':True,'firstRunSetup':True}),encoding='utf-8')
    finally:
        # Leave a failed installed app intact for CI diagnostics; successful test files only.
        if not app.exists():shutil.rmtree(testroot,ignore_errors=True)

if __name__=='__main__':main()
