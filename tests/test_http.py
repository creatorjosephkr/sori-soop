import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import app

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(app,'DATA',Path(self.tmp.name));self.patch.start()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.patch.stop();self.tmp.cleanup()
    def post(self,body,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(self.base+'/api/settings',json.dumps(body).encode(),headers))
    def test_settings_roundtrip(self):
        settings={'policy':'fixed','mode':'bgm','model':'small-music','seconds':40,'backend':'cpu'}
        with self.post(settings) as r:self.assertEqual(json.load(r)['settings'],settings)
        self.assertEqual(app.read_settings(),settings)
    def test_cross_origin_cannot_write(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.post({'policy':'auto','mode':'bgm'},'https://example.org')
        self.assertEqual(e.exception.code,403);e.exception.close()
    def test_unknown_audio_path_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.base+'/audio/../settings.json')
        self.assertEqual(e.exception.code,404);e.exception.close()


class SponsorTests(unittest.TestCase):
    setUp = HttpTests.setUp
    tearDown = HttpTests.tearDown

    def test_assets_and_default_browser_endpoint(self):
        for name,kind in [('spon.svg','image/svg+xml'),('kakaobank.png','image/png'),('paypal.png','image/png')]:
            with urllib.request.urlopen(self.base+'/spon/'+name) as response:
                self.assertEqual(response.headers['Content-Type'],kind)
                self.assertEqual(response.read(),(app.ROOT/'spon'/name).read_bytes())
        with patch.object(app,'open_paypal') as opener:
            with urllib.request.urlopen(urllib.request.Request(self.base+'/api/sponsor/paypal',b'{}')) as response:
                self.assertTrue(json.load(response)['ok'])
            opener.assert_called_once_with()
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(self.base+'/api/sponsor/paypal',b'{}',{'Origin':'https://example.org'}))
            self.assertEqual(error.exception.code,403);error.exception.close()
            self.assertEqual(opener.call_count,1)
        with patch.object(app,'open_paypal',side_effect=OSError('not available')):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(self.base+'/api/sponsor/paypal',b'{}'))
            self.assertEqual(error.exception.code,500);error.exception.close()

    def test_default_browser_commands_use_fixed_url(self):
        for system,command in [('Darwin','open'),('Linux','xdg-open')]:
            with patch.object(app.platform,'system',return_value=system),patch.object(app.subprocess,'run') as run:
                app.open_paypal()
                run.assert_called_once_with([command,app.PAYPAL_SPONSOR_URL],check=True,timeout=10)
        with patch.object(app.platform,'system',return_value='Windows'),patch.object(app.os,'startfile',create=True) as start:
            app.open_paypal();start.assert_called_once_with(app.PAYPAL_SPONSOR_URL)


class AudioRangeTests(unittest.TestCase):
    def test_audio_full_ranges_and_out_of_bounds(self):
        import engine
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine,'DATA',Path(tmp)):
            audio=Path(tmp)/'audio';audio.mkdir()
            ident='c'*32;(audio/(ident+'.wav')).write_bytes(b'0123456789')
            server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            url='http://127.0.0.1:'+str(server.server_port)+'/audio/'+ident+'.wav'
            try:
                for header,expected,code in [(None,b'0123456789',200),('bytes=2-5',b'2345',206),('bytes=7-',b'789',206),('bytes=-3',b'789',206)]:
                    request=urllib.request.Request(url,headers={'Range':header} if header else {})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status,code);self.assertEqual(response.read(),expected)
                        self.assertEqual(response.headers['Accept-Ranges'],'bytes')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=50-'}))
                self.assertEqual(error.exception.code,416);error.exception.close()
            finally:server.shutdown();server.server_close()


class RenameTests(unittest.TestCase):
    setUp = HttpTests.setUp
    tearDown = HttpTests.tearDown
    def test_legacy_result_rename_preserves_music_and_metadata(self):
        import engine
        with patch.object(engine,'DATA',Path(self.tmp.name)):
            ident='d'*32
            job={'id':ident,'status':'completed','createdAt':1,'prompt':'old description','settings':{'mode':'song'},'lyrics':'원래 가사'}
            engine.save(job)
            folder=engine.DATA/'audio';folder.mkdir();audio=folder/(ident+'.wav');audio.write_bytes(b'original audio')
            request=urllib.request.Request(self.base+'/api/rename',json.dumps({'id':ident,'title':'  새로운 제목  '}).encode(),{'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(json.load(response),{**job,'title':'새로운 제목'})
            self.assertEqual(json.loads((engine.DATA/'jobs'/(ident+'.json')).read_text(encoding='utf-8')),{**job,'title':'새로운 제목'})
            self.assertEqual(audio.read_bytes(),b'original audio')
            for payload,code in [({'id':ident,'title':' '},400),({'id':ident,'title':'a'*101},400),({'id':'../test','title':'x'},400),({'id':'e'*32,'title':'x'},404)]:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(self.base+'/api/rename',json.dumps(payload).encode()))
                self.assertEqual(error.exception.code,code);error.exception.close()
            with patch.object(engine,'ACTIVE',ident):
                with self.assertRaises(ValueError):engine.rename_result(ident,'진행 중')
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(self.base+'/api/rename',json.dumps({'id':ident,'title':'외부 수정'}).encode(),{'Origin':'https://example.org'}))
            self.assertEqual(error.exception.code,403);error.exception.close()
