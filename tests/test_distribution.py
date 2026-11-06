import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import engine
import installer
import runtime_download

class SourceArchiveTests(unittest.TestCase):
    def test_pinned_archive_extraction_is_scoped_and_idempotent(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            for name in ['repo/optimized/mlx/main.py','repo/optimized/tflite/main.py','repo/training/large.py','repo/LICENSE','repo/../../outside']:
                archive.writestr(name,'content')
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'runtime'
            with patch.object(runtime_download.urllib.request,'urlopen',return_value=io.BytesIO(stream.getvalue())):
                runtime_download.install_source('owner/repo','a'*40,destination,['optimized/mlx'])
            self.assertTrue((destination/'optimized/mlx/main.py').exists())
            self.assertTrue((destination/'LICENSE').exists())
            self.assertFalse((destination/'training').exists())
            self.assertFalse((Path(tmp)/'outside').exists())
            with patch.object(runtime_download.urllib.request,'urlopen') as network:
                runtime_download.install_source('owner/repo','a'*40,destination,['optimized/mlx']);network.assert_not_called()
            with self.assertRaises(RuntimeError):runtime_download.install_source('owner/repo','b'*40,destination)

class DistributionTests(unittest.TestCase):
    def test_frozen_engines_use_user_folder_instead_of_readonly_bundle(self):
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            env={**os.environ,'LOCAL_MUSIC_DATA':tmp,'LOCAL_MUSIC_RESOURCES':str(root)}
            env.pop('LOCAL_MUSIC_ENGINES',None)
            code="import sys;sys.frozen=True;import app_paths;print(app_paths.ENGINE_ROOT)"
            output=subprocess.check_output([sys.executable,'-c',code],cwd=root,env=env,text=True).strip()
            self.assertEqual(Path(output),Path(tmp)/'engines')
    def test_ui_and_release_version_match(self):
        root=Path(__file__).resolve().parent.parent;version=(root/'VERSION').read_text(encoding='utf-8').strip()
        self.assertIn('v'+version+'</small>',(root/'web/index.html').read_text(encoding='utf-8'))

class InstallerTests(unittest.TestCase):
    def test_only_known_components_and_no_install_during_generation(self):
        with self.assertRaises(ValueError):installer.start('../unknown')
        with tempfile.TemporaryDirectory() as tmp,patch.object(installer,'DATA',Path(tmp)),patch.object(installer,'uv_path',return_value=sys.executable),patch.object(installer.shutil,'disk_usage') as disk,patch.object(engine,'ACTIVE','a'*32):
            disk.return_value.free=100*1024**3
            with self.assertRaisesRegex(ValueError,'현재 작업'):installer.start('bgm')
    def test_generation_is_blocked_while_installing(self):
        settings={'mode':'bgm','model':'small-music','backend':'cpu','seconds':10,'policy':'manual'}
        with patch.object(engine,'ready',return_value=True),patch.object(installer,'STATE',{**installer.STATE,'active':True}):
            with self.assertRaisesRegex(ValueError,'모델 준비'):engine.start(settings,'Piano music',8)
