"""Local HTTP bridge. All CAD access is dispatched to the FreeCAD GUI thread."""
import hashlib
import json
import queue
import secrets
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from protocol import CommandError, validate_command


def start(open_browser=True):
    import FreeCAD as App
    import FreeCADGui as Gui
    from PySide import QtCore

    previous = getattr(App, '_web_ui_bridge', None)
    if previous:
        previous.stop()
    data = ROOT / 'local-data'
    data.mkdir(exist_ok=True)
    model_path = data / 'sample-board.FCStd'
    doc = next((d for d in App.listDocuments().values() if d.FileName == str(model_path)), None)
    if doc is None:
        if model_path.exists():
            doc = App.openDocument(str(model_path))
        else:
            doc = App.newDocument('WebUISampleBoard')
            doc.Label = 'Web UI sample board - TEST ONLY'
            board = doc.addObject('Part::Box', 'SampleBoard')
            board.Label = 'Sample board - TEST ONLY'
            board.Length, board.Width, board.Height = 355.6, 88.9, 38.1
            board.ViewObject.ShapeColor = (0.72, 0.52, 0.30)
            doc.recompute()
            doc.saveAs(str(model_path))
    App.setActiveDocument(doc.Name)
    view = Gui.activeDocument().activeView()
    animation = view.isAnimationEnabled()
    view.setAnimationEnabled(False)
    try:
        view.viewAxonometric()
        view.fitAll()
    finally:
        view.setAnimationEnabled(animation)

    class Bridge:
        def __init__(self):
            self.document = doc
            self.session = uuid.uuid4().hex
            self.token = secrets.token_urlsafe(32)
            self.revision = 0
            self.fingerprint = None
            self.saved_fingerprint = None
            self.file_stamp = None
            self.mesh = None
            self.commands = queue.Queue(maxsize=32)
            self.document.UndoMode = 1
            self.results = OrderedDict()
            self.stopped = False
            self.processing = False
            self.refresh()

        def refresh(self):
            if self.document.Name not in App.listDocuments() or App.listDocuments()[self.document.Name] is not self.document:
                raise CommandError('The sample document was closed. Run the macro again to reconnect.', 409)
            obj = self.document.getObject('SampleBoard')
            if obj is None:
                raise CommandError('SampleBoard is missing. Reopen the sample document.', 409)
            if any('Error' in str(state) or 'Invalid' in str(state) for state in obj.State):
                raise CommandError('FreeCAD reports an error in the sample board.', 422)
            if obj.Shape.isNull() or not obj.Shape.isValid():
                raise CommandError('FreeCAD reports invalid board geometry.', 422)
            dimensions = [obj.Length.Value, obj.Width.Value, obj.Height.Value]
            values = dimensions + list(obj.Placement.Base) + list(obj.Placement.Rotation.Q)
            signature = hashlib.sha256(repr(tuple(round(v, 8) for v in values)).encode()).hexdigest()
            if signature != self.fingerprint:
                self.revision += 1
                self.fingerprint = signature
                vertices, triangles = obj.Shape.tessellate(0.3)
                self.mesh = {'vertices': [coordinate for v in vertices for coordinate in (v.x, v.y, v.z)],
                             'indices': [index for t in triangles for index in t]}
            stamp = model_path.stat().st_mtime_ns if model_path.exists() else None
            if stamp != self.file_stamp:
                self.file_stamp = stamp
                try:
                    with ZipFile(model_path) as archive:
                        root = ET.fromstring(archive.read('Document.xml'))
                    properties = root.find(".//ObjectData/Object[@name='SampleBoard']/Properties")
                    saved_values = [float(properties.find("Property[@name='%s']/Float" % key).attrib['value']) for key in ('Length','Width','Height')]
                    placement = properties.find("Property[@name='Placement']/PropertyPlacement").attrib
                    saved_values += [float(placement[key]) for key in ('Px','Py','Pz','Q0','Q1','Q2','Q3')]
                    self.saved_fingerprint = hashlib.sha256(repr(tuple(round(v, 8) for v in saved_values)).encode()).hexdigest()
                except (OSError, ValueError, AttributeError, KeyError):
                    self.saved_fingerprint = None
            return obj, dimensions

        def snapshot(self):
            obj, dimensions = self.refresh()
            return {'session': self.session, 'revision': self.revision,
                    'document': self.document.Label, 'object': obj.Name, 'label': obj.Label,
                    'dimensionsMm': dict(zip(('length', 'width', 'height'), dimensions)),
                    'saved': self.fingerprint == self.saved_fingerprint,
                    'saveScope': 'sample board geometry',
                    'mesh': self.mesh, 'freecadVersion': '.'.join(App.Version()[:3]),
                    'modelFile': model_path.name}

        def execute(self, body):
            request_id = body.get('requestId') if isinstance(body, dict) else None
            # Cache failures as well as successes so retries never reapply an uncertain edit.
            encoded = json.dumps(body, sort_keys=True)
            if isinstance(request_id, str) and request_id in self.results:
                prior_body, result = self.results[request_id]
                if prior_body != encoded:
                    return 409, {'error': 'Request identifier reused with different data.'}
                return result
            try:
                self.refresh()
                command = validate_command(body, self.session, self.revision)
                if command['operation'] == 'save':
                    self.document.save()
                    self.saved_fingerprint = self.fingerprint
                    self.file_stamp = model_path.stat().st_mtime_ns
                else:
                    obj = self.document.getObject('SampleBoard')
                    self.document.openTransaction('Web UI: change board length')
                    try:
                        obj.Length = command['lengthMm']
                        self.document.recompute()
                        if obj.Shape.isNull() or not obj.Shape.isValid() or len(obj.Shape.Solids) != 1:
                            raise CommandError('The resulting board is not a valid solid.', 422)
                        if any('Error' in str(state) or 'Invalid' in str(state) for state in obj.State):
                            raise CommandError('FreeCAD could not recompute the board.', 422)
                        self.document.commitTransaction()
                    except Exception:
                        self.document.abortTransaction()
                        self.document.recompute()
                        raise
                result = (200, self.snapshot())
            except CommandError as exc:
                result = (exc.status, {'error': str(exc)})
            except Exception as exc:
                result = (500, {'error': 'FreeCAD operation failed: ' + str(exc)})
            if isinstance(request_id, str):
                self.results[request_id] = (encoded, result)
                while len(self.results) > 128:
                    self.results.popitem(last=False)
            return result

        def process(self):
            # Guard against nested Qt event loops in FreeCAD commands.
            if self.processing or self.stopped:
                return
            self.processing = True
            try:
                self.process_pending()
            finally:
                self.processing = False

        def process_pending(self):
            # Runs on the GUI thread, never on the HTTP worker thread.
            for _ in range(8):
                try:
                    action, payload, reply, deadline = self.commands.get_nowait()
                except queue.Empty:
                    return
                if time.monotonic() > deadline:
                    reply.put((503, {'error': 'Request expired before reaching FreeCAD.'}))
                    continue
                try:
                    result = (200, self.snapshot()) if action == 'snapshot' else self.execute(payload)
                except CommandError as exc:
                    result = (exc.status, {'error': str(exc)})
                except Exception as exc:
                    result = (500, {'error': str(exc)})
                reply.put(result)

        def stop(self):
            self.stopped = True
            self.timer.stop()
            self.server.shutdown()
            self.server.server_close()

    bridge = Bridge()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log session credentials or local model data.

        def respond(self, status, data, content_type='application/json'):
            encoded = json.dumps(data).encode() if content_type == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed(self, authenticated=False):
            host = self.headers.get('Host', '')
            if host != '127.0.0.1:8765':
                self.respond(403, {'error': 'Invalid host.'})
                return False
            origin = self.headers.get('Origin')
            if origin and origin != 'http://127.0.0.1:8765':
                self.respond(403, {'error': 'Invalid origin.'})
                return False
            if authenticated and not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + bridge.token):
                self.respond(401, {'error': 'Open the viewer link from FreeCAD to authorize this session.'})
                return False
            return True

        def dispatch(self, action, payload=None):
            reply = queue.Queue(maxsize=1)
            try:
                bridge.commands.put_nowait((action, payload, reply, time.monotonic() + 8))
                status, result = reply.get(timeout=10)
            except queue.Full:
                status, result = 503, {'error': 'FreeCAD is busy. Retry shortly.'}
            except queue.Empty:
                status, result = 503, {'error': 'FreeCAD did not respond. Refresh before retrying; the change may have applied.'}
            self.respond(status, result)

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.allowed(path.startswith('/api/')):
                return
            if path == '/api/snapshot':
                self.dispatch('snapshot')
                return
            files = {'/': (ROOT/'web/index.html', 'text/html; charset=utf-8'),
                     '/app.js': (ROOT/'web/app.js', 'text/javascript'),
                     '/style.css': (ROOT/'web/style.css', 'text/css'),
                     '/vendor/three.module.js': (ROOT/'node_modules/three/build/three.module.js', 'text/javascript'),
                     '/vendor/three.core.js': (ROOT/'node_modules/three/build/three.core.js', 'text/javascript')}
            if path not in files:
                self.respond(404, {'error': 'Not found.'})
                return
            file, mime = files[path]
            try:
                self.respond(200, file.read_bytes(), mime)
            except FileNotFoundError:
                self.respond(503, {'error': 'Missing web files. Run npm install in the repository.'})

        def do_POST(self):
            if not self.allowed(True):
                return
            if urlsplit(self.path).path != '/api/command':
                self.respond(404, {'error': 'Not found.'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('Invalid request size.')
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Expected application/json.')
                body = json.loads(self.rfile.read(size))
            except (ValueError, json.JSONDecodeError) as exc:
                self.respond(400, {'error': str(exc)})
                return
            self.dispatch('command', body)

    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    server.daemon_threads = True
    bridge.server = server
    bridge.timer = QtCore.QTimer()
    bridge.timer.timeout.connect(bridge.process)
    bridge.timer.start(40)
    bridge.thread = threading.Thread(target=server.serve_forever, daemon=True)
    bridge.thread.start()
    App._web_ui_bridge = bridge  # Retain timer and bridge for the lifetime of the session.
    url = 'http://127.0.0.1:8765/#token=' + bridge.token
    (data/'viewer-url.txt').write_text(url)
    (data/'viewer-url.txt').chmod(0o600)
    print('FreeCAD Web UI running at http://127.0.0.1:8765/; authorized link is in local-data/viewer-url.txt')
    if open_browser:
        from PySide import QtGui
        try:
            from PySide import QtWidgets
        except ImportError:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
    return bridge
