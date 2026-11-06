import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import app_paths


class BootstrapTests(unittest.TestCase):
    def test_windows_uses_bundled_interpreter_and_copy_venv(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);python=root/'runtime-python/python.exe';python.parent.mkdir();python.touch()
            venv=root/'engines/test/.venv';venv.mkdir(parents=True);marker=venv/'keep-package';marker.write_text('keep')
            with patch.object(app_paths,'ROOT',root),patch.dict(os.environ,{},clear=True),patch('subprocess.run') as run:
                self.assertEqual(app_paths.bootstrap_python(),str(python))
                app_paths.create_venv(venv)
                run.assert_called_once()
                self.assertEqual(run.call_args.args[0],[str(python),'-m','venv','--without-pip','--copies',str(venv)])
                self.assertTrue(run.call_args.kwargs['check'])
                self.assertEqual(marker.read_text(),'keep')

    def test_missing_frozen_windows_python_does_not_download_again(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(app_paths,'ROOT',Path(folder)),patch.dict(os.environ,{},clear=True),patch.object(app_paths.sys,'platform','win32'),patch.object(app_paths.sys,'frozen',True,create=True):
            with self.assertRaisesRegex(RuntimeError,'다시 설치'):app_paths.bootstrap_python()
