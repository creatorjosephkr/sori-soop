import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import app
import engine
from song_duration import plan_options,planned_seconds,explicit_bpm,check_planned_bpm


class SongDurationTests(unittest.TestCase):
    def test_auto_removes_seconds_for_every_settings_policy(self):
        for policy in ('auto','fixed','manual'):
            selected={'policy':policy,'mode':'song','model':'ace-step','backend':'cpu','seconds':90,'durationMode':'auto'}
            settings=app.resolve_generation_settings(app.validate(selected),{'ramGB':16,'availableGB':8,'appleSilicon':False})
            self.assertIsNone(settings['seconds'])
            self.assertEqual(plan_options(settings),{'target_duration':None,'user_metadata':None})
            self.assertEqual(selected['seconds'],90)
        with self.assertRaises(ValueError):app.validate({'policy':'auto','mode':'bgm','durationMode':'auto'})

    def test_auto_uses_plan_not_character_estimate_or_hidden_slider(self):
        settings={'mode':'song','durationMode':'auto','seconds':30}
        self.assertEqual(planned_seconds(settings,{'duration':87},''),87)
        self.assertEqual(planned_seconds(settings,{},'<|audio_code_1|>'*150),30)
        for value in (601,9):
            with self.assertRaises(ValueError):planned_seconds(settings,{'duration':value},'')
        with self.assertRaises(ValueError):planned_seconds(settings,{},'')
        self.assertEqual(planned_seconds({'mode':'song','seconds':45},{'duration':87},''),45)

    def test_engine_accepts_chosen_length_and_keeps_auto_request_unset(self):
        script_text="""import argparse,json,wave
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--out');a,_=p.parse_known_args()
job=json.loads(Path(a.request).read_text());assert job['settings']['seconds'] is None
with wave.open(a.out,'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(8000);w.writeframes(bytes(12*8000*4))
"""
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);script=root/'song.py';script.write_text(script_text,encoding='utf-8')
            with patch.object(engine,'DATA',root),patch.object(engine,'ready',return_value=True),patch.object(engine,'song_paths',return_value=(root,Path(sys.executable),script)):
                try:
                    job=engine.start({'mode':'song','model':'ace-step','backend':'cpu','seconds':None,'durationMode':'auto'},'warm piano',16,lyrics='New lyrics')
                    deadline=time.monotonic()+10
                    while engine.ACTIVE and time.monotonic()<deadline:time.sleep(.02)
                    self.assertIsNone(engine.ACTIVE)
                    self.assertEqual(job['status'],'completed',job.get('error'))
                    self.assertEqual(job['durationSeconds'],12)
                    self.assertIsNone(job['settings']['seconds'])
                finally:engine.cancel()

class ExplicitTempoTests(unittest.TestCase):
    def test_requested_bpm_overrides_auto_metadata_without_setting_duration(self):
        settings={'mode':'song','durationMode':'auto','seconds':None}
        for text in ('Warm ballad, 72 BPM.','BPM: 72','72bpm','72 BPM. Keep 72 BPM.'):
            self.assertEqual(plan_options(settings,text),{'target_duration':None,'user_metadata':{'bpm':72}})
        self.assertEqual(plan_options({'mode':'song','seconds':300},'72 BPM'),{'target_duration':300,'user_metadata':{'duration':300,'bpm':72}})

    def test_ambiguous_or_invalid_tempo_is_not_silently_changed(self):
        for text in ('80-100 BPM','80 - 100 BPM','warm ballad','about 72.5 BPM'):
            self.assertIsNone(explicit_bpm(text))
        for text in ('72 BPM then 120 BPM','20 BPM','BPM: 900'):
            with self.assertRaises(ValueError):explicit_bpm(text)
        check_planned_bpm(72,{'bpm':72})
        check_planned_bpm(None,{'bpm':201})
        for metadata in ({'bpm':201},{'bpm':None},{}):
            with self.assertRaisesRegex(ValueError,'일치하지'):check_planned_bpm(72,metadata)
