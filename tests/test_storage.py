import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app_paths
import storage


class StorageTests(unittest.TestCase):
    def test_external_mac_bundle_uses_sibling_not_bundle_or_home(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'External'/'Apps'/'SoriSoop.app'/'Contents'/'MacOS'/'SoriSoop'
            self.assertEqual(app_paths.installed_storage(path,'darwin'),Path(folder).resolve()/'External'/'Apps'/'SoriSoop Data')

    def test_executable_folder_for_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            binary=Path(folder)/'SoriSoop'/'SoriSoop.exe'
            self.assertEqual(app_paths.installed_storage(binary,'win32'),binary.resolve().parent/'SoriSoop Data')

    def test_runtime_and_caches_follow_selected_drive(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{},clear=True),patch.object(storage,'STORAGE',Path(folder)/'SoriSoop Data'),patch.object(storage,'ENGINE_ROOT',Path(folder)/'SoriSoop Data'/'engines'):
            storage.prepare()
            self.assertTrue(storage.ENGINE_ROOT.is_dir())
            for key in ('HF_HOME','HF_HUB_CACHE','UV_CACHE_DIR','UV_PYTHON_INSTALL_DIR','UV_TOOL_DIR','UV_PYTHON_BIN_DIR'):
                self.assertTrue(Path(os.environ[key]).is_relative_to(storage.STORAGE))
            self.assertEqual(storage.describe()['root'],str(storage.STORAGE))
            self.assertGreater(storage.describe()['freeBytes'],0)
            self.assertFalse(list(storage.STORAGE.glob('.write-check-*')))

    def test_readonly_location_reports_path_without_silent_fallback(self):
        with patch.object(storage,'STORAGE',Path('/Volumes/ReadOnly/SoriSoop Data')),patch.object(Path,'mkdir',side_effect=PermissionError('read-only')):
            with self.assertRaisesRegex(RuntimeError,'/Volumes/ReadOnly/SoriSoop Data'):storage.prepare()
