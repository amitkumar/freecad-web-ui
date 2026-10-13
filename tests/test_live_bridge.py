"""Opt-in integration checks against the running synthetic-board prototype.
Run: FREECAD_LIVE_TEST=1 python3 -m unittest discover -s tests -v
"""
import json
import os
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen
import uuid
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('FREECAD_LIVE_TEST') == '1', 'Requires the running FreeCAD sample-board bridge')
class LiveBridgeTests(unittest.TestCase):
    def setUp(self):
        link = (ROOT/'local-data/viewer-url.txt').read_text().strip()
        self.token = parse_qs(urlsplit(link).fragment)['token'][0]
        self.base = 'http://127.0.0.1:8765'

    def request(self, path='/api/snapshot', body=None, token=True, headers=None):
        hdr = {'Authorization': 'Bearer ' + self.token} if token else {}
        if headers: hdr.update(headers)
        if body is not None: hdr['Content-Type'] = 'application/json'
        req = Request(self.base+path, data=json.dumps(body).encode() if body is not None else None, headers=hdr)
        try:
            with urlopen(req, timeout=15) as response: return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def command(self, state, operation='set_length', **values):
        return dict(operation=operation, session=state['session'],revision=state['revision'],requestId=uuid.uuid4().hex,**values)

    def test_auth_and_origin(self):
        self.assertEqual(self.request(token=False)[0],401)
        self.assertEqual(self.request(headers={'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request(headers={'Host':'example.com'})[0],403)
        self.assertEqual(self.request('/bridge/freecad_web_bridge.py')[0],404)
        self.assertEqual(self.request('/local-data/viewer-url.txt')[0],404)

    def test_edit_duplicate_stale_validation_and_save(self):
        status, before = self.request()
        self.assertEqual(status,200)
        self.assertEqual(before['object'],'SampleBoard')
        original = before['dimensionsMm']['length']
        changed = original + 25.4 if original < 2000 else original - 25.4
        edit = self.command(before,lengthMm=changed)
        status, after = self.request('/api/command', edit)
        self.assertEqual(status,200,after)
        self.assertAlmostEqual(after['dimensionsMm']['length'],changed)
        self.assertFalse(after['saved'])
        self.assertGreater(after['revision'],before['revision'])
        self.assertAlmostEqual(max(after['mesh']['vertices'][0::3])-min(after['mesh']['vertices'][0::3]),changed)
        self.assertEqual(self.request('/api/command',edit),(200,after))
        stale = self.command(before,lengthMm=original)
        self.assertEqual(self.request('/api/command',stale)[0],409)
        invalid = self.command(after,lengthMm=-1)
        self.assertEqual(self.request('/api/command',invalid)[0],400)
        self.assertEqual(self.request()[1]['revision'],after['revision'])
        status, restored = self.request('/api/command',self.command(after,lengthMm=original))
        self.assertEqual(status,200,restored)
        status, saved = self.request('/api/command',self.command(restored,operation='save'))
        self.assertEqual(status,200,saved)
        self.assertTrue(saved['saved'])
        with ZipFile(ROOT/'local-data/sample-board.FCStd') as archive:
            root = ET.fromstring(archive.read('Document.xml'))
            value = root.find(".//ObjectData/Object[@name='SampleBoard']/Properties/Property[@name='Length']/Float")
            self.assertAlmostEqual(float(value.attrib['value']),original)
