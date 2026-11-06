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
