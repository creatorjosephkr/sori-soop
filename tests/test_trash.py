import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import engine

class TrashTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.patch=patch.object(engine,'DATA',self.root);self.patch.start()
    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()
    def archive(self,ident,mode='song',instrumental=False):
        engine.save({'id':ident,'title':'보관된 제목','status':'completed','createdAt':1,'settings':{'mode':mode,'instrumental':instrumental}})
        audio=self.root/'audio';audio.mkdir(exist_ok=True)
        (audio/(ident+'.wav')).write_bytes(b'audio')
        (audio/(ident+'.mp3')).write_bytes(b'mp3')
        engine.delete_result(ident)
    def test_list_and_empty_only_confirmed_entries(self):
        first,second,active='a'*32,'b'*32,'c'*32
        self.archive(first,instrumental=True);self.archive(second,mode='bgm')
        engine.save({'id':active,'status':'completed'})
        entries=engine.trash_history()
        entry=next(item for item in entries if item['id']==first)
        self.assertEqual(entry['kind'],'instrumental')
        self.assertEqual(entry['title'],'보관된 제목')
        self.assertGreater(entry['bytes'],8)
        self.assertEqual(engine.empty_trash([first,first]),{'ok':True,'count':1,'errors':[]})
        self.assertFalse((self.root/'trash'/first).exists())
        self.assertTrue((self.root/'trash'/second/(second+'.wav')).exists())
        self.assertTrue((self.root/'jobs'/(active+'.json')).exists())
    def test_invalid_ids_never_delete(self):
        self.archive('a'*32)
        for ids in (None,[],['../jobs'],['a'*32,'invalid']):
            with self.assertRaises(ValueError):engine.empty_trash(ids)
        self.assertEqual(len(engine.trash_history()),1)
    def test_corrupt_record_remains_visible_and_can_be_emptied(self):
        self.archive('a'*32)
        (self.root/'trash'/('a'*32)/('a'*32+'.json')).write_text('bad json')
        self.assertEqual(engine.trash_history()[0]['kind'],'unknown')
        self.assertEqual(engine.empty_trash(['a'*32])['count'],1)
    def test_symlink_cannot_delete_external_data(self):
        external=self.root/'external';external.mkdir();(external/'keep').write_text('keep')
        trash=self.root/'trash';trash.mkdir()
        try:(trash/('a'*32)).symlink_to(external,target_is_directory=True)
        except OSError as error:self.skipTest('Symbolic links are unavailable: '+str(error))
        self.assertEqual(engine.trash_history(),[])
        self.assertEqual(engine.empty_trash(['a'*32])['errors'],['a'*32])
        self.assertTrue((external/'keep').exists())
    def test_partial_failure_is_reported_and_remaining_entries_processed(self):
        import shutil
        self.archive('a'*32);self.archive('b'*32)
        original=shutil.rmtree
        def remove(path,*args,**kwargs):
            if Path(path).name=='a'*32:raise PermissionError('denied')
            return original(path,*args,**kwargs)
        with patch.object(shutil,'rmtree',side_effect=remove):
            result=engine.empty_trash(['a'*32,'b'*32])
        self.assertFalse(result['ok']);self.assertEqual(result['count'],1)
        self.assertTrue((self.root/'trash'/('a'*32)).exists())
