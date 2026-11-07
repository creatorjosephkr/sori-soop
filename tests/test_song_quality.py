import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
import app
import engine
import installer
import song_runtime

class QualityPlannerTests(unittest.TestCase):
    def test_choice_persists_without_changing_old_settings(self):
        old={'policy':'auto','mode':'song','durationMode':'auto'}
        self.assertNotIn('songQuality',app.validate(old))
        self.assertEqual(app.validate({**old,'songQuality':'quality'})['songQuality'],'quality')
        with self.assertRaises(ValueError):app.validate({**old,'songQuality':'other'})

    def test_quality_requires_complete_model_and_enough_available_memory(self):
        settings={'policy':'manual','mode':'song','model':'ace-step','backend':'cpu','seconds':30,'songQuality':'quality'}
        with patch.object(engine,'planner_ready',return_value=False):
            with self.assertRaisesRegex(ValueError,'먼저 준비'):engine.start(settings,'piano',16,lyrics='New lyrics')
        with patch.object(engine,'planner_ready',return_value=True):
            with self.assertRaisesRegex(ValueError,'8GB'):engine.start(settings,'piano',6,lyrics='New lyrics')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'checkpoints/acestep-5Hz-lm-1.7B';path.mkdir(parents=True)
            (path/'model.safetensors').write_bytes(b'weights')
            self.assertFalse(song_runtime.planner_ready(root,'quality'))
            for name in ('config.json','tokenizer.json','tokenizer_config.json'):(path/name).write_text('{}')
            self.assertTrue(song_runtime.planner_ready(root,'quality'))
            self.assertFalse(song_runtime.planner_ready(root,'invalid'))

    def test_first_run_never_downloads_optional_quality_model(self):
        state={'active':False,'state':'idle','ready':{'bgm':False,'translation':False,'song':False},'optionalReady':{'song-quality':False}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(installer,'DATA',Path(tmp)),patch.object(installer,'status',return_value=state),patch.object(installer,'STATE',dict(state)),patch.object(engine,'ACTIVE',None),patch.object(installer.storage,'prepare'),patch.object(installer,'uv_path',return_value='uv'),patch.object(installer.threading,'Thread') as thread:
            installer.start('auto')
            self.assertEqual(thread.call_args.kwargs['args'],(['bgm','translation','song'],))
            with self.assertRaisesRegex(ValueError,'기본 실행 준비'):installer.start('song-quality')

    def test_optional_failure_does_not_persist_as_first_run_failure(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(installer,'DATA',Path(tmp)),patch.object(installer,'STATE',{'active':True,'state':'installing'}),patch.object(installer.shutil,'disk_usage') as disk,patch.object(installer,'run',side_effect=RuntimeError('download failed')):
            disk.return_value.free=100*1024**3
            installer.run_queue(['song-quality'])
            self.assertEqual(installer.STATE['state'],'failed')
            self.assertIsNone(installer.saved_error())
