"""Build the local platform's desktop bundle and distributable, without model weights."""
import hashlib
import importlib.metadata
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
VERSION=(ROOT/'VERSION').read_text(encoding='utf-8').strip()

def main():
    if f'v{VERSION}</small>' not in (ROOT/'web/index.html').read_text(encoding='utf-8'):raise RuntimeError('화면 버전과 VERSION 파일이 다릅니다.')
    from PIL import Image
    import uv
    image=Image.open(ROOT/'assets/app-icon.png')
    icon=ROOT/'assets'/('app-icon.icns' if sys.platform=='darwin' else 'app-icon.ico')
    image.save(icon)
    licenses=ROOT/'build/third-party-licenses';shutil.rmtree(licenses,ignore_errors=True);licenses.mkdir(parents=True)
    for dist in importlib.metadata.distributions():
        for entry in dist.files or []:
            if Path(entry).suffix.lower() in ('','.txt','.md','.rst','.html') and any(word in Path(entry).name.lower() for word in ('license','copying','notice')):
                source=Path(dist.locate_file(entry))
                if source.is_file():
                    target=licenses/dist.metadata['Name']/Path(entry).name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.exists():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--noupx','--name','SoriSoop','--icon',str(icon),'--distpath',str(ROOT/'dist'),'--workpath',str(ROOT/'build/pyinstaller')]
    for name in ('numpy','soundfile','torch','transformers','ctranslate2','sentencepiece','pytest'):
        args+=['--exclude-module',name]
    resources=['web','runners','app_paths.py','storage.py','model_download.py','audio_processing.py','translation.py','runtime_download.py','setup_engine.py','setup_song.py','setup_translation.py','VERSION','LICENSE','THIRD_PARTY_NOTICES.txt']
    resources+=[p.name for p in ROOT.glob('*-version.txt')]
    resources+=[p.name for p in ROOT.glob('requirements-*.lock')]+['requirements-translation.txt']
    for name in resources:args+=['--add-data',str(ROOT/name)+':'+(name if (ROOT/name).is_dir() else '.')]
    for name in ('spon.svg','kakaobank.png','paypal.png'):args+=['--add-data',str(ROOT/'spon'/name)+':spon']
    args+=['--add-data',str(licenses)+':third-party-licenses','--add-binary',str(uv.find_uv_bin())+':tools']
    if sys.platform=='darwin':args+=['--osx-bundle-identifier','com.creatorjoseph.sorisoop','--target-architecture','arm64']
    if sys.platform=='win32':
        numbers=tuple(int(part) for part in VERSION.split('.'))+(0,)
        fields={'CompanyName':'크리에이터 요셉','FileDescription':'소리숲','FileVersion':VERSION,'InternalName':'SoriSoop','OriginalFilename':'SoriSoop.exe','ProductName':'소리숲','ProductVersion':VERSION,'LegalCopyright':'Copyright © 2026 크리에이터 요셉'}
        strings=','.join('StringStruct('+repr(key)+','+repr(value)+')' for key,value in fields.items())
        version_file=ROOT/'build/windows-version.txt'
        version_file.write_text('VSVersionInfo(ffi=FixedFileInfo(filevers='+repr(numbers)+',prodvers='+repr(numbers)+",mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('041204b0',["+strings+"])]),VarFileInfo([VarStruct('Translation',[1042,1200])])])",encoding='utf-8')
        args+=['--version-file',str(version_file)]
    args+=[str(ROOT/'desktop.py')]
    subprocess.run(args,cwd=ROOT,check=True)
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    if sys.platform=='darwin':
        bundle=ROOT/'dist/SoriSoop.app'
        info=bundle/'Contents/Info.plist'
        with info.open('rb') as stream:config=plistlib.load(stream)
        config.update(CFBundleDisplayName='소리숲',CFBundleShortVersionString=VERSION,CFBundleVersion=VERSION,LSMinimumSystemVersion='14.0',NSHighResolutionCapable=True)
        with info.open('wb') as stream:plistlib.dump(config,stream)
        subprocess.run(['codesign','--force','--deep','--sign','-',str(bundle)],check=True)
        subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
        staging=ROOT/'build/dmg';shutil.rmtree(staging,ignore_errors=True);staging.mkdir()
        shutil.copytree(bundle,staging/'SoriSoop.app',symlinks=True);(staging/'Applications').symlink_to('/Applications')
        shutil.copy2(ROOT/'RELEASE_README.txt',staging/'먼저 읽어주세요.txt')
        artifact=artifacts/f'SoriSoop-{VERSION}-macos-arm64.dmg'
        artifact.unlink(missing_ok=True)
        subprocess.run(['hdiutil','create','-volname','소리숲 '+VERSION,'-srcfolder',str(staging),'-ov','-format','UDZO',str(artifact)],check=True)
    elif sys.platform=='win32':
        shutil.copy2(ROOT/'RELEASE_README.txt',ROOT/'dist/SoriSoop/먼저 읽어주세요.txt')
        artifact=Path(shutil.make_archive(str(artifacts/f'SoriSoop-{VERSION}-windows-x64'),'zip',ROOT/'dist','SoriSoop'))
    else:raise RuntimeError('macOS 또는 Windows에서 빌드하세요.')
    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
    (artifacts/(artifact.name+'.sha256')).write_text(digest+'  '+artifact.name+'\n', encoding='utf-8')
    print(json.dumps({'artifact':str(artifact),'sha256':digest}))

if __name__=='__main__':main()
