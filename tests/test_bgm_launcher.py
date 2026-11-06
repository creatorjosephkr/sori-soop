import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch


class BgmLauncherTests(unittest.TestCase):
    def test_windows_color_initialization_does_not_launch_empty_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            script=Path(folder)/'sa3_tflite.py'
            script.write_text("import os\nfrom types import SimpleNamespace\nP=SimpleNamespace()\nos.system('')\ndef main():\n assert os.system('normal-command')==17\n",encoding='utf-8')
            def system(command):
                if command=='':raise AssertionError('Empty shell launched')
                return 17
            try:
                with patch.object(sys,'platform','win32'),patch.object(sys,'argv',['bgm.py','--script',str(script)]),patch.object(sys,'path',list(sys.path)),patch.object(os,'system',side_effect=system) as shell:
                    runpy.run_path(str(Path(__file__).resolve().parent.parent/'runners/bgm.py'),run_name='__main__')
                    shell.assert_called_once_with('normal-command')
                    self.assertIs(os.system,shell)
            finally:sys.modules.pop('local_bgm_upstream',None)
