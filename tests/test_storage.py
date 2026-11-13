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
            with self.assertRaises(RuntimeError) as error:storage.prepare()
            self.assertIn(str(storage.STORAGE),str(error.exception))

    def test_clean_session_caches_removes_transient_files_and_preserves_audio_wav(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            audio = data / 'audio'
            jobs = data / 'jobs'
            audio.mkdir()
            jobs.mkdir()
            wav = audio / 'song.wav'
            wav.write_bytes(b'RIFF....WAVE')
            mp3 = audio / 'song.mp3'
            mp3.write_bytes(b'ID3....')
            tmp_audio = audio / 'partial.tmp'
            tmp_audio.write_text('tmp')
            work_dir = audio / 'song-work'
            work_dir.mkdir()
            (work_dir / 'chunk.bin').write_bytes(b'123')
            tmp_job = jobs / 'job.tmp'
            tmp_job.write_text('tmp')
            job_json = jobs / 'job.json'
            job_json.write_text('{"id":"job"}')

            storage.clean_session_caches(data)

            self.assertTrue(wav.is_file())
            self.assertTrue(job_json.is_file())
            self.assertFalse(mp3.exists())
            self.assertFalse(tmp_audio.exists())
            self.assertFalse(work_dir.exists())
            self.assertFalse(tmp_job.exists())

