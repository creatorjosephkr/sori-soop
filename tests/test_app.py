import unittest
from app import recommend, validate

class SettingsTests(unittest.TestCase):
    def test_low_memory_recommends_short_single_job(self):
        r = recommend({'ramGB': 8, 'availableGB': 2, 'appleSilicon': True})
        self.assertEqual((r['model'], r['seconds'], r['batchSize']), ('small-music', 30, 1))
        self.assertIsNone(r['estimatedTime'])
        self.assertTrue(r['warnings'])

    def test_available_memory_overrides_total(self):
        self.assertEqual(recommend({'ramGB': 32, 'availableGB': 2})['seconds'], 30)

    def test_manual_duration_limits(self):
        with self.assertRaises(ValueError):
            validate({'policy': 'manual', 'mode': 'bgm', 'model': 'small-music', 'backend': 'cpu', 'seconds': 130})

    def test_song_requires_vocal_model(self):
        with self.assertRaises(ValueError):
            validate({'policy': 'manual', 'mode': 'song', 'model': 'small-music', 'backend': 'cpu', 'seconds': 30})

    def test_manual_values_are_preserved(self):
        s = {'policy': 'manual', 'mode': 'song', 'model': 'ace-step', 'backend': 'cpu', 'seconds': 90}
        self.assertEqual(validate(s), s)

    def test_medium_bgm_and_sfx_mode_validation(self):
        medium = {'policy': 'manual', 'mode': 'bgm', 'model': 'medium', 'backend': 'apple', 'seconds': 300}
        self.assertEqual(validate(medium)['model'], 'medium')
        with self.assertRaises(ValueError):
            validate({**medium, 'seconds': 381})
        sfx = {'policy': 'manual', 'mode': 'sfx', 'model': 'small-sfx', 'backend': 'cpu', 'seconds': 3}
        self.assertEqual(validate(sfx)['mode'], 'sfx')
        with self.assertRaises(ValueError):
            validate({'policy': 'manual', 'mode': 'sfx', 'model': 'small-music', 'backend': 'cpu', 'seconds': 5})
        self.assertEqual(recommend({'ramGB': 16, 'availableGB': 8, 'appleSilicon': True}, 'sfx')['model'], 'small-sfx')
        self.assertEqual(recommend({'ramGB': 16, 'availableGB': 8, 'appleSilicon': True}, 'sfx')['seconds'], 5)

if __name__ == '__main__':
    unittest.main()

class AutoDurationTests(unittest.TestCase):
    def test_auto_keeps_selected_song_duration(self):
        from app import resolve_generation_settings
        settings=validate({'policy':'auto','mode':'song','seconds':180})
        resolved=resolve_generation_settings(settings,{'ramGB':16,'availableGB':5,'appleSilicon':True})
        self.assertEqual(resolved['seconds'],180)
        self.assertEqual(resolved['model'],'ace-step')
        self.assertEqual(resolved['backend'],'apple')
        self.assertNotIn('model',settings)

    def test_auto_without_selected_duration_uses_recommendation(self):
        from app import resolve_generation_settings
        resolved=resolve_generation_settings(validate({'policy':'auto','mode':'song'}),{'ramGB':16,'availableGB':5,'appleSilicon':True})
        self.assertEqual(resolved['seconds'],30)

    def test_auto_rejects_out_of_range_or_non_integer_duration(self):
        for mode,seconds in [('song',601),('bgm',130),('song',True),('song','60'),('song',0)]:
            with self.assertRaises(ValueError):validate({'policy':'auto','mode':mode,'seconds':seconds})
