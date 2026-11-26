import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import tradingview_oauth as oauth
class OAuthRefreshTests(unittest.TestCase):
    def setup_private(self,directory):
        root=Path(directory)
        (root/'oauth-client.json').write_text(json.dumps({'client_id':'fake-public-client'}))
        original=dict(access_token='fake-old',refresh_token='fake-refresh-old',token_type='Bearer',
            scope='mcp:read mcp:tools',obtained_at=0,expires_in=600)
        oauth.private_write(root/'oauth-token.json',original)
        return root,original
    def test_refresh_rotation_is_private_and_audience_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root,_=self.setup_private(directory)
            response=Mock(status_code=200)
            response.json.return_value=dict(access_token='fake-new',refresh_token='fake-refresh-new',
                token_type='Bearer',scope='mcp:read mcp:tools',expires_in=600)
            with patch.object(oauth,'ROOT',root),patch.object(oauth.requests,'post',return_value=response) as post:
                self.assertEqual(oauth.access_token(),'fake-new')
                self.assertEqual(oauth.access_token(),'fake-new')
                self.assertEqual(post.call_count,1)
                self.assertEqual(post.call_args.kwargs['data']['resource'],oauth.RESOURCE)
                self.assertFalse(post.call_args.kwargs['allow_redirects'])
            stored=json.loads((root/'oauth-token.json').read_text())
            self.assertEqual(stored['refresh_token'],'fake-refresh-new')
            self.assertEqual(os.stat(root/'oauth-token.json').st_mode&0o777,0o600)
    def test_refresh_failure_keeps_previous_credential_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root,original=self.setup_private(directory)
            with patch.object(oauth,'ROOT',root),patch.object(oauth.requests,'post',return_value=Mock(status_code=401)):
                with self.assertRaisesRegex(RuntimeError,'refresh failed: HTTP 401'):oauth.access_token()
            self.assertEqual(json.loads((root/'oauth-token.json').read_text()),original)
