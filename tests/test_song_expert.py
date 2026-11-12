import unittest
from pathlib import Path
import app
import song_expert

ROOT=Path(__file__).resolve().parent.parent

class SongExpertTests(unittest.TestCase):
    def test_defaults_match_previous_fixed_values(self):
        self.assertEqual(song_expert.normalize(None),{'inferenceSteps':8,'shift':3.0,'inferMethod':'ode','sampler':'euler','dcw':True,'lmTemperature':0.85,'lmCfgScale':2.0,'lmTopP':0.9})
        self.assertTrue(song_expert.is_default({}))

    def test_partial_values_fill_defaults(self):
        value=song_expert.normalize({'inferenceSteps':12,'sampler':'heun'})
        self.assertEqual((value['inferenceSteps'],value['sampler'],value['shift']),(12,'heun',3.0))

    def test_rejects_invalid_values(self):
        for bad in ({'inferenceSteps':30},{'inferenceSteps':8.5},{'shift':'3'},{'inferMethod':'x'},{'dcw':1},{'lmTopP':1.2},{'unknown':1},[],{'lmTemperature':float('nan')}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):song_expert.normalize(bad)

    def test_settings_persist_normalized(self):
        saved=app.validate({'policy':'auto','mode':'song','durationMode':'auto','songExpert':{'inferenceSteps':6}})
        self.assertEqual(saved['songExpert']['inferenceSteps'],6)
        self.assertEqual(saved['songExpert']['lmCfgScale'],2.0)
        with self.assertRaises(ValueError):app.validate({'policy':'auto','mode':'song','songExpert':{'shift':9}})

    def test_runner_uses_expert_values(self):
        source=(ROOT/'runners/song.py').read_text(encoding='utf-8')
        for token in ("inference_steps=expert['inferenceSteps']","shift=expert['shift']","sampler_mode=expert['sampler']","dcw_enabled=expert['dcw']","temperature=expert['lmTemperature']","cfg_scale=expert['lmCfgScale']","top_p=expert['lmTopP']"):
            self.assertIn(token,source)

    def test_ui_presets_and_help_use_svg(self):
        html=(ROOT/'web/index.html').read_text(encoding='utf-8')
        js=(ROOT/'web/expert-settings.js').read_text(encoding='utf-8')
        self.assertIn('id="expert-body" class="expert-body" hidden',html)
        self.assertLess(html.index('id="expert-settings"'),html.index('id="warnings"'))
        self.assertIn('/expert-settings.js',html)
        self.assertIn("icon('help')",js)

if __name__=='__main__':unittest.main()
