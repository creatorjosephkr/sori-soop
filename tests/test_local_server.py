import errno
import json
import socket
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch
import app
from local_server import backend_session,bind_server

class LocalServerTests(unittest.TestCase):
    def test_occupied_port_uses_free_port_without_interrupting_occupant(self):
        with socket.socket() as occupant,tempfile.TemporaryDirectory() as tmp:
            occupant.bind(('127.0.0.1',0));occupant.listen(1)
            preferred=occupant.getsockname()[1]
            with backend_session(app.Handler,Path(tmp),preferred) as session:
                self.assertTrue(session.owned)
                self.assertNotEqual(session.server.server_port,preferred)
                with urllib.request.urlopen(session.url+'/api/session') as response:
                    self.assertEqual(json.load(response)['app'],'sori-soop')
                self.assertEqual(occupant.getsockname()[1],preferred)
    def test_same_data_folder_reuses_backend_and_does_not_close_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            with backend_session(app.Handler,Path(tmp),0) as owner:
                with backend_session(app.Handler,Path(tmp),0) as second:
                    self.assertFalse(second.owned);self.assertEqual(second.url,owner.url)
                with urllib.request.urlopen(owner.url+'/api/session') as response:self.assertEqual(response.status,200)
    def test_restart_retains_selected_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            with backend_session(app.Handler,Path(tmp),0) as first:port=first.server.server_port
            with backend_session(app.Handler,Path(tmp),8765) as second:self.assertEqual(second.server.server_port,port)
    def test_other_bind_errors_are_not_hidden(self):
        with patch('local_server.LocalHTTPServer',side_effect=PermissionError(errno.EACCES,'denied')) as server:
            with self.assertRaises(PermissionError):bind_server(app.Handler,8765)
            self.assertEqual(server.call_count,1)
