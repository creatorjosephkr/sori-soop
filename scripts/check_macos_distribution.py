"""Verify the final DMG, including the read-only app users actually download."""
import argparse
import plistlib
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('image');args=parser.parse_args()
    image=Path(args.image).resolve();version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
    subprocess.run(['hdiutil','verify',str(image)],check=True)
    with tempfile.TemporaryDirectory(prefix='sorisup-distribution-') as mount:
        subprocess.run(['hdiutil','attach','-readonly','-nobrowse','-mountpoint',mount,str(image)],check=True)
        try:
            app=Path(mount)/'SoriSoop.app';binary=app/'Contents/MacOS/SoriSoop'
            info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
            assert info['CFBundleShortVersionString']==version
            assert subprocess.check_output(['lipo','-archs',str(binary)],text=True).strip()=='arm64'
            subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
            for flag,name in [('--self-test','macos-server.json'),('--smoke-ui','macos-window.json')]:
                subprocess.run([str(binary),flag,'--report',str(ROOT/'artifacts'/name)],check=True)
        finally:subprocess.run(['hdiutil','detach',mount],check=True)
    print('Final macOS distribution verified')

if __name__=='__main__':main()
