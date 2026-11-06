import io
import json
import unittest
from unittest.mock import patch
import updates


def release(tag='v1.0.2'):
    name=f'SoriSoop-{tag[1:]}-macos-arm64.dmg'
    return {'tag_name':tag,'html_url':updates.REPOSITORY+'/releases/tag/'+tag,
            'draft':False,'prerelease':False,'assets':[{'name':name,'state':'uploaded',
            'browser_download_url':updates.REPOSITORY+'/releases/download/'+tag+'/'+name}]}


class UpdateTests(unittest.TestCase):
    def test_numeric_comparison_and_only_stable_versions(self):
        self.assertGreater(updates.version('v1.10.0'),updates.version('1.9.9'))
        for tag in ('1.0.0-beta','v1.0','junk','01.0.0'):
            with self.assertRaises(ValueError):updates.version(tag)
        with patch.object(updates,'CURRENT','1.0.2'):
            self.assertFalse(updates.release_info(release())['available'])
            self.assertFalse(updates.release_info(release('v1.0.1'))['available'])
            self.assertTrue(updates.release_info(release('v1.0.3'))['available'])
        for flag in ('draft','prerelease'):
            item=release();item[flag]=True
            with self.assertRaises(ValueError):updates.release_info(item)

    def test_download_is_platform_specific_and_official(self):
        with patch.object(updates.platform,'system',return_value='Darwin'),patch.object(updates.platform,'machine',return_value='arm64'):
            self.assertTrue(updates.release_info(release())['downloadUrl'].endswith('macos-arm64.dmg'))
            item=release();item['assets'][0]['browser_download_url']='https://evil.example/app.dmg'
            self.assertIsNone(updates.release_info(item)['downloadUrl'])
        with patch.object(updates.platform,'system',return_value='Windows'),patch.object(updates.platform,'machine',return_value='AMD64'):
            item=release();asset=item['assets'][0]
            for key in ('name','browser_download_url'):asset[key]=asset[key].replace('macos-arm64.dmg','windows-x64.zip')
            self.assertTrue(updates.release_info(item)['downloadUrl'].endswith('windows-x64.zip'))
            setup=dict(asset)
            for key in ('name','browser_download_url'):setup[key]=setup[key].replace('windows-x64.zip','windows-x64-setup.exe')
            item['assets'].append(setup)
            self.assertTrue(updates.release_info(item)['downloadUrl'].endswith('windows-x64-setup.exe'))
        item=release();item['html_url']='https://evil.example/release'
        with self.assertRaises(ValueError):updates.release_info(item)

    def test_check_is_cached_and_sends_no_user_content(self):
        with patch.object(updates,'_cached',None),patch.object(updates,'_checked_at',0),patch.object(updates.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(release()).encode())) as network:
            self.assertEqual(updates.check(),updates.check());network.assert_called_once()
            request=network.call_args.args[0]
            self.assertEqual(request.full_url,updates.LATEST)
            self.assertIsNone(request.data)
            self.assertNotIn('Authorization',request.headers)

    def test_network_failure_can_retry(self):
        with patch.object(updates,'_cached',None),patch.object(updates.urllib.request,'urlopen',side_effect=OSError('offline')) as network:
            for _ in range(2):
                with self.assertRaises(OSError):updates.check()
            self.assertEqual(network.call_count,2)
