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
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
VERSION=(ROOT/'VERSION').read_text(encoding='utf-8').strip()


def build_open_folder_app(staging_dir, version):
    from PIL import Image, ImageDraw
    app_dir = staging_dir / '다른 폴더 열기.app'
    shutil.rmtree(app_dir, ignore_errors=True)
    macos_dir = app_dir / 'Contents' / 'MacOS'
    res_dir = app_dir / 'Contents' / 'Resources'
    macos_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    # Generate custom folder-open icon (1024x1024 supersampled from 2048x2048)
    sz = 2048
    img = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, 'RGBA')
    def s(v):
        return v * (sz / 24.0)
    # Soft sage squircle background
    draw.rounded_rectangle([s(1.5), s(1.5), sz - s(1.5), sz - s(1.5)], radius=s(5.2), fill=(232, 242, 228, 255), outline=(146, 182, 140, 255), width=int(s(0.7)))
    # Folder tab & body
    draw.rounded_rectangle([s(4.5), s(6.2), s(11.5), s(10.5)], radius=s(1.3), fill=(68, 116, 84, 255))
    draw.rounded_rectangle([s(4.5), s(8.0), s(19.5), s(18.0)], radius=s(1.8), fill=(86, 142, 104, 255))
    draw.rounded_rectangle([s(4.5), s(9.6), s(19.5), s(18.0)], radius=s(1.6), fill=(116, 174, 132, 255))
    # Plus / open badge in center of folder
    cx, cy = s(12.0), s(13.8)
    r = s(2.4)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(246, 250, 244, 255))
    lw = int(s(0.65))
    draw.line([(cx - s(1.1), cy), (cx + s(1.1), cy)], fill=(42, 84, 58, 255), width=lw)
    draw.line([(cx, cy - s(1.1)), (cx, cy + s(1.1))], fill=(42, 84, 58, 255), width=lw)

    icon_png = img.resize((1024, 1024), Image.Resampling.LANCZOS)
    icns_path = res_dir / 'folder-open.icns'
    iconset = ROOT / 'build/folder-open.iconset'
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir(parents=True, exist_ok=True)
    for pt in (16, 32, 128, 256, 512):
        icon_png.resize((pt, pt), Image.Resampling.LANCZOS).save(iconset / f'icon_{pt}x{pt}.png', format='PNG')
        icon_png.resize((pt * 2, pt * 2), Image.Resampling.LANCZOS).save(iconset / f'icon_{pt}x{pt}@2x.png', format='PNG')
    try:
        subprocess.run(['iconutil', '-c', 'icns', '-o', str(icns_path), str(iconset)], check=True)
    except Exception:
        icon_png.save(icns_path)
    shutil.rmtree(iconset, ignore_errors=True)

    info_plist = {
        'CFBundleName': '다른 폴더 열기',
        'CFBundleDisplayName': '다른 폴더 열기',
        'CFBundleIdentifier': 'com.creatorjoseph.sorisoop.openfolder',
        'CFBundleVersion': version,
        'CFBundleShortVersionString': version,
        'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': 'open_other_folder',
        'CFBundleIconFile': 'folder-open',
        'LSMinimumSystemVersion': '14.0',
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
    }
    with (app_dir / 'Contents' / 'Info.plist').open('wb') as f:
        plistlib.dump(info_plist, f)

    script = '''#!/bin/sh
DMG_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
APP_SRC="$DMG_DIR/SoriSoop.app"
/usr/bin/osascript - "$APP_SRC" <<'APPLESCRIPT'
on run argv
    set appSrc to item 1 of argv
    try
        set chosenFolder to choose folder with prompt "소리숲(SoriSoop)을 설치하거나 열 다른 폴더를 선택하세요:"
    on error
        return
    end try
    set targetPosix to POSIX path of chosenFolder
    try
        set dialogRes to display dialog "선택한 폴더(" & targetPosix & ")에 소리숲을 바로 복사해 설치할까요, 아니면 폴더만 열까요?" buttons {"취소", "폴더만 열기", "여기에 바로 설치"} default button "여기에 바로 설치" with title "소리숲 다른 폴더 설치"
    on error
        return
    end try
    set btn to button returned of dialogRes
    if btn is "폴더만 열기" then
        tell application "Finder"
            open chosenFolder
            activate
        end tell
    else if btn is "여기에 바로 설치" then
        do shell script "/usr/bin/ditto " & quoted form of appSrc & " " & quoted form of (targetPosix & "SoriSoop.app")
        tell application "Finder"
            open chosenFolder
            try
                select POSIX file (targetPosix & "SoriSoop.app")
            end try
            activate
        end tell
    end if
end run
APPLESCRIPT
'''
    exe_path = macos_dir / 'open_other_folder'
    exe_path.write_text(script, encoding='utf-8')
    exe_path.chmod(0o755)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app_dir)], check=True)
    subprocess.run(['SetFile', '-a', 'E', str(app_dir)], check=False)


def build_dmg_background(out_path, version):
    from PIL import Image, ImageDraw, ImageFont
    scale = 2
    w, h = 740 * scale, 430 * scale
    img = Image.new('RGBA', (w, h), (242, 246, 238, 255))
    draw = ImageDraw.Draw(img, 'RGBA')

    # Soft vertical forest-sage gradient background
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(244 - 16 * t)
        g = int(248 - 14 * t)
        b = int(241 - 16 * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    # Subtle outer card frame
    pad = 16 * scale
    draw.rounded_rectangle(
        [pad, pad, w - pad, h - pad],
        radius=20 * scale,
        fill=(250, 252, 248, 210),
        outline=(198, 216, 190, 255),
        width=2 * scale,
    )

    font_path = ROOT / 'web/fonts/NotoSansKR-Variable.ttf'
    def load_font(size, weight=None):
        try:
            f = ImageFont.truetype(str(font_path), size * scale)
            if weight is not None and hasattr(f, 'set_variation_by_axes'):
                try:
                    f.set_variation_by_axes([weight])
                except Exception:
                    pass
            return f
        except Exception:
            return ImageFont.load_default()

    font_title = load_font(23, 750)
    font_sub = load_font(13, 500)
    font_guide = load_font(13.5, 700)
    font_tip = load_font(11, 450)

    # Header title & subtitle
    title_text = f'소리숲 · SoriSoop v{version}'
    sub_text = '내 컴퓨터 안에서 직접 만드는 로컬 AI 음악 · 보컬 스튜디오'
    draw.text((w // 2, 42 * scale), title_text, font=font_title, fill=(33, 64, 46, 255), anchor='mm')
    draw.text((w // 2, 70 * scale), sub_text, font=font_sub, fill=(88, 112, 95, 255), anchor='mm')

    # Cards: SoriSoop.app (145), Applications (435), 다른 폴더 열기 (605)
    for cx in (145 * scale, 435 * scale):
        cy = 198 * scale
        rx, ry = 74 * scale, 82 * scale
        draw.rounded_rectangle(
            [cx - rx, cy - ry, cx + rx, cy + ry],
            radius=22 * scale,
            fill=(255, 255, 255, 225),
            outline=(194, 214, 186, 255),
            width=2 * scale,
        )

    # Secondary card for '다른 폴더 열기' button on the right
    ocx, ocy = 605 * scale, 198 * scale
    orx, ory = 74 * scale, 82 * scale
    draw.rounded_rectangle(
        [ocx - orx, ocy - ory, ocx + orx, ocy + ory],
        radius=22 * scale,
        fill=(238, 245, 234, 225),
        outline=(180, 204, 172, 255),
        width=2 * scale,
    )

    # Center arrow badge + chevrons pointing Left (145) -> Right (435)
    ax, ay = 290 * scale, 192 * scale
    draw.rounded_rectangle(
        [ax - 48 * scale, ay - 21 * scale, ax + 48 * scale, ay + 21 * scale],
        radius=21 * scale,
        fill=(225, 238, 220, 255),
        outline=(176, 204, 166, 255),
        width=2 * scale,
    )
    chevron_colors = [
        (120, 162, 132, 180),
        (76, 126, 92, 220),
        (42, 90, 62, 255),
    ]
    offsets = [-20 * scale, 0, 20 * scale]
    for dx, col in zip(offsets, chevron_colors):
        cx = ax + dx
        pts = [
            (cx - 6 * scale, ay - 10 * scale),
            (cx + 5 * scale, ay),
            (cx - 6 * scale, ay + 10 * scale),
        ]
        draw.line(pts, fill=col, width=4 * scale, joint='curve')

    # Bottom instruction banner
    bx1, by1, bx2, by2 = 40 * scale, 322 * scale, w - 40 * scale, 392 * scale
    draw.rounded_rectangle(
        [bx1, by1, bx2, by2],
        radius=14 * scale,
        fill=(228, 239, 223, 255),
        outline=(188, 210, 178, 255),
        width=2 * scale,
    )
    guide_text = "소리숲 아이콘을 Applications로 드래그하거나 오른쪽 '다른 폴더 열기'를 실행하세요"
    tip_text = "처음 실행 시 보안 안내가 뜨면 앱 아이콘을 우클릭(Control+클릭)한 뒤 '열기'를 선택해 주세요"
    draw.text((w // 2, 346 * scale), guide_text, font=font_guide, fill=(36, 70, 50, 255), anchor='mm')
    draw.text((w // 2, 371 * scale), tip_text, font=font_tip, fill=(82, 108, 88, 255), anchor='mm')

    final_img = img.resize((740, 430), Image.Resampling.LANCZOS).convert('RGB')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(out_path, format='PNG', dpi=(72, 72))


def main():
    if f'v{VERSION}</small>' not in (ROOT/'web/index.html').read_text(encoding='utf-8'):raise RuntimeError('화면 버전과 VERSION 파일이 다릅니다.')
    from PIL import Image
    import uv
    image=Image.open(ROOT/'assets/app-icon.png')
    icon=ROOT/'assets'/('app-icon.icns' if sys.platform=='darwin' else 'app-icon.ico')
    if sys.platform=='darwin':
        iconset=ROOT/'build/app-icon.iconset'
        shutil.rmtree(iconset,ignore_errors=True);iconset.mkdir(parents=True,exist_ok=True)
        for pt in (16,32,128,256,512):
            image.resize((pt,pt),Image.Resampling.LANCZOS).save(iconset/f'icon_{pt}x{pt}.png',format='PNG')
            image.resize((pt*2,pt*2),Image.Resampling.LANCZOS).save(iconset/f'icon_{pt}x{pt}@2x.png',format='PNG')
        try:
            subprocess.run(['iconutil','-c','icns','-o',str(icon),str(iconset)],check=True)
        except Exception:
            image.save(icon)
    else:
        image.save(icon,sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
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
    resources=['web','runners','app_paths.py','storage.py','model_download.py','song_runtime.py','song_duration.py','song_expert.py','song_lyrics.py','exaone_lyrics.py','qwen_tts_voice.py','audio_processing.py','audio_export.py','translation.py','runtime_download.py','setup_engine.py','setup_song.py','setup_song_quality.py','setup_translation.py','setup_bootstrap_check.py','VERSION','LICENSE','THIRD_PARTY_NOTICES.txt']
    resources+=[p.name for p in ROOT.glob('*-version.txt')]
    resources+=[p.name for p in ROOT.glob('requirements-*.lock')]+['requirements-translation.txt']
    for name in resources:args+=['--add-data',str(ROOT/name)+':'+(name if (ROOT/name).is_dir() else '.')]
    for name in ('spon.svg','kakaobank.png','paypal.png'):args+=['--add-data',str(ROOT/'spon'/name)+':spon']
    args+=['--add-data',str(licenses)+':third-party-licenses','--add-binary',str(uv.find_uv_bin())+':tools']
    if sys.platform=='darwin':args+=['--osx-bundle-identifier','com.creatorjoseph.sorisoop','--target-architecture','arm64']
    if sys.platform=='win32':
        # Only the build host downloads Python; user machines receive ordinary files.
        python_root=ROOT/'build/windows-python'
        subprocess.run([str(uv.find_uv_bin()),'python','install','3.11.18','--install-dir',str(python_root),'--no-bin','--no-registry'],check=True)
        source=python_root/'cpython-3.11.18-windows-x86_64-none'
        subprocess.run([str(source/'python.exe'),'-c','import ssl,venv;print("Bundled Python ready")'],check=True)
        runtime=ROOT/'build/windows-runtime-python';shutil.rmtree(runtime,ignore_errors=True)
        shutil.copytree(source,runtime,symlinks=False)
        args+=['--add-data',str(runtime)+':runtime-python']
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
        build_open_folder_app(staging, VERSION)
        shutil.copy2(ROOT/'RELEASE_README.txt',staging/'먼저 읽어주세요.txt')
        subprocess.run(['SetFile','-a','V',str(staging/'먼저 읽어주세요.txt')],check=False)
        bg_path=staging/'.background'/'background.png'
        build_dmg_background(bg_path, VERSION)
        shutil.copy2(icon,staging/'.VolumeIcon.icns')
        subprocess.run(['SetFile','-a','C',str(staging)],check=False)
        rw_dmg=ROOT/'build'/'SoriSoop-rw.dmg'
        rw_dmg.unlink(missing_ok=True)
        volname='소리숲 '+VERSION
        subprocess.run(['hdiutil','create','-volname',volname,'-srcfolder',str(staging),'-ov','-format','UDRW',str(rw_dmg)],check=True)
        mount_dir=Path('/Volumes')/volname
        if mount_dir.exists():
            subprocess.run(['hdiutil','detach',str(mount_dir),'-force'],check=False)
        subprocess.run(['hdiutil','attach','-readwrite','-noverify','-noautoopen',str(rw_dmg)],check=True)
        try:
            applescript = f'''
            tell application "Finder"
                tell disk "{volname}"
                    open
                    set current view of container window to icon view
                    set toolbar visible of container window to false
                    set statusbar visible of container window to false
                    set the bounds of container window to {{180, 140, 920, 598}}
                    set viewOptions to the icon view options of container window
                    set arrangement of viewOptions to not arranged
                    set icon size of viewOptions to 96
                    set text size of viewOptions to 13
                    set background picture of viewOptions to file ".background:background.png"
                    set position of item "SoriSoop.app" of container window to {{145, 190}}
                    set position of item "Applications" of container window to {{435, 190}}
                    try
                        set position of item "다른 폴더 열기.app" of container window to {{605, 190}}
                    end try
                    try
                        set position of item ".background" of container window to {{1000, 1000}}
                    end try
                    try
                        set position of item ".VolumeIcon.icns" of container window to {{1000, 1000}}
                    end try
                    try
                        set position of item ".fseventsd" of container window to {{1000, 1000}}
                    end try
                    close
                    open
                    update without registering applications
                    delay 1
                    close
                end tell
            end tell
            '''
            try:
                subprocess.run(['osascript','-e',applescript],check=False,timeout=30)
            except Exception:
                pass
            subprocess.run(['sync'],check=False)
            time.sleep(1)
        finally:
            subprocess.run(['hdiutil','detach',str(mount_dir),'-force'],check=True)
        artifact=artifacts/f'SoriSoop-{VERSION}-macos-arm64.dmg'
        artifact.unlink(missing_ok=True)
        subprocess.run(['hdiutil','convert',str(rw_dmg),'-format','UDZO','-imagekey','zlib-level=9','-o',str(artifact)],check=True)
        rw_dmg.unlink(missing_ok=True)
    elif sys.platform=='win32':
        shutil.copy2(ROOT/'RELEASE_README.txt',ROOT/'dist/SoriSoop/먼저 읽어주세요.txt')
        subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'scripts/prepare_windows_dependencies.ps1')],check=True)
        manifest=json.loads((ROOT/'build/prerequisites/manifest.json').read_text(encoding='utf-8-sig'))
        vc=next(item for item in manifest if item['name']=='vc_redist.x64.exe')['version'].split('.')
        compiler=shutil.which('ISCC.exe') or str(Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Inno Setup 6/ISCC.exe')
        subprocess.run([compiler,'/DRepoRoot='+str(ROOT),'/DAppVersion='+VERSION,'/DVCMajor='+vc[0],'/DVCMinor='+vc[1],'/DVCBuild='+vc[2],str(ROOT/'installer/windows/setup.iss')],check=True)
        artifact=artifacts/f'SoriSoop-{VERSION}-windows-x64-setup.exe'
        shutil.copy2(ROOT/'build/prerequisites/manifest.json',artifacts/'windows-prerequisites.json')
    else:raise RuntimeError('macOS 또는 Windows에서 빌드하세요.')
    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
    (artifacts/(artifact.name+'.sha256')).write_text(digest+'  '+artifact.name+'\n', encoding='utf-8')
    print(json.dumps({'artifact':str(artifact),'sha256':digest}))

if __name__=='__main__':main()
