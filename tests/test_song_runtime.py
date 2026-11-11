import json
from pathlib import Path
import tempfile
import unittest
import song_runtime


class SongRuntimeTests(unittest.TestCase):
    def test_windows_ready_requires_check_marker_and_matching_package_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertFalse(song_runtime.ready(root))
            (root/'.sorisup-song-runtime.json').write_text(json.dumps({'revision':song_runtime.REVISION,'versions':song_runtime.VERSIONS}))
            for name,version in song_runtime.VERSIONS.items():
                metadata=root/'.venv/Lib/site-packages'/(name+'-'+version+'.dist-info')/'METADATA';metadata.parent.mkdir(parents=True)
                metadata.write_text('Name: '+name+'\nVersion: '+version+'\n')
            self.assertTrue(song_runtime.ready(root))
            metadata.write_text('Name: '+name+'\nVersion: 0.0.0\n')
            self.assertFalse(song_runtime.ready(root))

    def test_detect_nvidia_gpu_parsing(self):
        from unittest.mock import patch
        with patch.object(song_runtime.subprocess, 'check_output', return_value='NVIDIA GeForce RTX 5050 Laptop GPU, 8192, 572.16\n'):
            gpu = song_runtime.detect_nvidia_gpu()
            self.assertIsNotNone(gpu)
            self.assertEqual(gpu['name'], 'NVIDIA GeForce RTX 5050 Laptop GPU')
            self.assertEqual(gpu['vramGB'], 8.0)
            self.assertEqual(gpu['driver'], '572.16')

    def test_detect_nvidia_gpu_none_when_command_fails(self):
        from unittest.mock import patch
        with patch.object(song_runtime.subprocess, 'check_output', side_effect=OSError('not found')):
            self.assertIsNone(song_runtime.detect_nvidia_gpu())

    def test_cpu_installation_is_not_cuda_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = {'revision': song_runtime.REVISION, 'backend': 'cpu', 'cuda': False,
                      'versions': song_runtime.VERSIONS}
            report = root / '.sorisup-song-runtime.json'
            report.write_text(json.dumps(marker))
            for name, version in song_runtime.VERSIONS.items():
                metadata = root / '.venv/Lib/site-packages' / (name+'-'+version+'.dist-info') / 'METADATA'
                metadata.parent.mkdir(parents=True)
                metadata.write_text('Version: '+version+'\n')
            self.assertTrue(song_runtime.ready(root, 'cpu'))
            self.assertFalse(song_runtime.ready(root, 'cuda'))
            marker.update(backend='cuda', cuda=True)
            report.write_text(json.dumps(marker))
            self.assertTrue(song_runtime.ready(root, 'cuda'))
            marker['revision'] = 'windows-runtime-v2'
            report.write_text(json.dumps(marker))
            self.assertFalse(song_runtime.ready(root, 'cuda'))
            self.assertTrue(song_runtime.ready(root, 'cpu'))

    def test_required_cuda_rejects_cpu_before_loading_models(self):
        from unittest.mock import Mock, patch
        import sys
        torch = Mock()
        torch.cuda.is_available.return_value = False
        with patch.dict(sys.modules, {'torch': torch, 'torchvision': Mock(), 'torchaudio': Mock()}), \
             patch('importlib.metadata.version', return_value='test'):
            with self.assertRaisesRegex(RuntimeError, 'CUDA'):
                song_runtime.validate_native(Path('.'), require_cuda=True)

    def test_cuda_kernel_failure_is_not_accepted_as_ready(self):
        from unittest.mock import Mock, patch
        import sys
        torch = Mock()
        torch.cuda.is_available.return_value = True
        torch.ones.side_effect = RuntimeError('no kernel image is available')
        with patch.dict(sys.modules, {'torch': torch, 'torchvision': Mock(), 'torchaudio': Mock()}), \
             patch('importlib.metadata.version', return_value='test'):
            with self.assertRaisesRegex(RuntimeError, 'no kernel image'):
                song_runtime.validate_native(Path('.'), require_cuda=True)

    def test_windows_setup_requires_gpu_runtime_for_detected_nvidia(self):
        from unittest.mock import patch
        import engine, installer
        with patch.object(installer.platform, 'system', return_value='Windows'), \
             patch.object(song_runtime, 'detect_nvidia_gpu', return_value={'vramGB': 8}), \
             patch.object(engine, 'ready', return_value=True) as ready, \
             patch.object(engine, 'planner_ready', return_value=True), \
             patch.object(installer, 'bgm_weights_ready', return_value=True), \
             patch.object(installer, 'saved_error', return_value=None):
            installer.status()
            ready.assert_any_call('cuda', 'ace-step')
