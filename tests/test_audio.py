import tempfile
import unittest
from pathlib import Path
from audio_processing import validate_peak_db, wav_peak_db
try:
    import numpy as np
except ImportError:
    np = None

class PeakSettingsTests(unittest.TestCase):
    def test_peak_limits_and_invalid_values(self):
        from app import validate, resolve_generation_settings
        for value in (-24,-6,0):
            settings=validate({'policy':'auto','mode':'song','peakDb':value})
            resolved=resolve_generation_settings(settings,{'ramGB':16,'availableGB':6,'appleSilicon':True})
            self.assertEqual(resolved['peakDb'],value)
        for value in (True,None,'-6',1,-25,float('nan'),float('inf')):
            with self.assertRaises(ValueError):validate_peak_db(value)

@unittest.skipUnless(np is not None, 'Run audio tests with the installed generation Python environment')
class AudioPeakTests(unittest.TestCase):
    def test_raw_overload_attenuated_without_flattening_waveform(self):
        from audio_processing import limit_peak
        raw=np.array([[0, .5, 1, 2, -2], [0, .1, .2, .4, -.4]],dtype=np.float32)
        output=limit_peak(raw,-6)
        self.assertLessEqual(float(abs(output).max()),10**(-6/20))
        np.testing.assert_allclose(output,raw*(output[0,3]/2),atol=1e-7)
        self.assertNotEqual(output[0,1],output[0,2])

    def test_quiet_and_silent_audio_are_not_amplified(self):
        from audio_processing import limit_peak
        for raw in (np.zeros((2,100),dtype=np.float32),np.full((2,100),.01,dtype=np.float32)):
            np.testing.assert_array_equal(limit_peak(raw,-6),raw)

    def test_non_finite_audio_rejected(self):
        from audio_processing import limit_peak
        for raw in (np.array([np.nan]),np.array([np.inf]),np.array([])):
            with self.assertRaises(ValueError):limit_peak(raw,-6)

    def test_pcm_file_meets_requested_peak_and_retains_stereo_duration(self):
        import wave
        from audio_processing import write_wav
        raw=np.stack([np.sin(np.arange(48000)/25)*1.8,np.cos(np.arange(48000)/25)*.9]).astype(np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            for peak in (-6,-12,0):
                path=Path(tmp)/'out.wav';write_wav(path,raw,48000,peak)
                measured=wav_peak_db(path)
                self.assertLessEqual(measured,peak)
                self.assertAlmostEqual(measured,peak,places=2)
                with wave.open(str(path)) as w:
                    self.assertEqual((w.getnchannels(),w.getnframes(),w.getframerate()),(2,48000,48000))
