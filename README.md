# FreeCAD Web UI

A local WebGL interface for a real FreeCAD sample board. Change its length in the browser; FreeCAD recomputes the solid and returns its geometry. FreeCAD remains the single source of truth.

## Prototype 01

Implemented:

- Live tessellated geometry from a named FreeCAD `Part::Box`.
- Browser orbit, zoom, top/isometric views, and automatic framing after length changes.
- Length editing in inches, converted to millimeters before submission.
- FreeCAD transactions and shape validation for edits.
- Session/revision checks to reject stale commands; request IDs prevent duplicate application.
- One-second refresh to observe changes made directly in FreeCAD.
- An explicit **Save model** action and saved-state comparison against the FCStd file.
- Loopback-only serving, per-session authorization, origin/host checks, and a fixed operation allowlist.

The sample starts at 14 × 3.5 × 1.5 inches. Length is limited to 1–96 inches. Existing saved sample dimensions are preserved on later launches.

## Run locally

Prerequisites: the FreeCAD desktop application, Node.js/npm for installing Three.js, and a browser with WebGL.

1. In this repository, run:

   ```sh
   npm ci
   ```

2. In FreeCAD, choose **File → Open** and open `bridge/StartWebUI.FCMacro`.
3. Choose **Macro → Execute Macro**. It opens or creates the sample FCStd file and opens an authorized viewer in your default browser.
4. Enter a length, select **Apply in FreeCAD**, then **Save model** to persist it.

The server runs inside FreeCAD at `http://127.0.0.1:8765/`. Keep FreeCAD running. The authorized viewer link is also stored in ignored `local-data/viewer-url.txt`; treat it as a local credential. After opening the authorized link once, plain viewer links work in other tabs of the same browser profile. Authorization is stored only for this local origin and is validated by FreeCAD on every request. A FreeCAD restart still requires opening the new authorized link.

If FreeCAD restarts, execute the macro again and use the newly opened viewer. If port 8765 is already occupied by another application, startup fails rather than selecting an unexpected address. Re-executing the macro replaces its previous bridge session.

To stop the bridge without quitting FreeCAD, run this in FreeCAD's Python console:

```python
App._web_ui_bridge.stop()
```

## Isolated macOS launcher (additional launch path)

After installing dependencies, double-click **Open Board Studio.command** in this repository. It starts the dedicated sample-board session with `QT_ACCESSIBILITY=0`, separate settings under `local-data/runtime/user.cfg`, and recovery storage under `local-data/runtime/recovery`. Initial settings disable navigation animations. Existing settings and recovery data are preserved.

The launcher refuses to start if any `freecad` process is already running or port 8765 is occupied. It never terminates another process. Arrange a session handoff first, then save and close FreeCAD yourself before starting it. Do not run it during another design session's live operation.

The accessibility workaround applies only to this launched process and can reduce screen-reader and native UI-automation access. Browser interaction uses the bridge and does not depend on native accessibility. This is a mitigation for the observed Qt/macOS crash, not a product fix.

Preview the launch plan without creating runtime files or starting FreeCAD:

```sh
python3 launch.py --dry-run
```

Launcher safeguards have unit tests. On October 14, 2026, an approved temporary-copy test also verified isolated startup on FreeCAD 1.1.4 with `QT_ACCESSIBILITY=0`, direct edits, stale rejection, undo/redo, save/close/reopen, browser edit/save, and graceful child-process exit. See `docs/validation.md` for the test boundary.

To request the native synthetic-board smoke test during an ordinary isolated launch:

```sh
python3 launch.py --smoke-test
```

The default running-process and occupied-port checks still apply. Test startup writes ignored `local-data/launch-report.json` and `local-data/smoke-report.json`; no session credentials are included in these reports. Manual `StartWebUI.FCMacro` launch remains supported, but cannot change Qt's already-initialized startup environment.

## Single source of truth

```text
Browser commands → local request queue → FreeCAD document → display mesh → browser
```

All document operations run on FreeCAD's GUI thread. The browser cannot execute arbitrary Python, open arbitrary files, or edit a second model. Camera changes are local viewer preferences. Saving writes `local-data/sample-board.FCStd`.

The saved indicator covers this sample board's dimensions and placement, not unrelated document metadata. Mesh data is derived and disposable. This prototype is limited to the dedicated sample board; it is not an editor for arbitrary CAD documents.

## Tests

Pure protocol checks (Python 3.9+):

```sh
python3 -m unittest discover -s tests -v
```

Opt-in live integration checks, after launching the macro:

```sh
FREECAD_LIVE_TEST=1 python3 -m unittest discover -s tests -v
```

Live checks temporarily change the synthetic board, restore its original length, and save it. They cover authorization, origin/host checks, private-file isolation, invalid values, stale commands, duplicate requests, exported mesh dimensions, and persistence in FCStd XML.

For a separate FreeCAD-side check of direct edits, undo/redo, and save/close/reopen, open and execute `tests/FreeCADSmoke.FCMacro` after starting the bridge. It restores the original sample length and writes an ignored `local-data/smoke-report.json` when successful.

## Current limitations

- Single local user and a single synthetic board; no apartment files are included.
- Polling HTTP transport, not WebSockets or multiuser synchronization.
- No general sketch, face/edge, constraint, material, or manufacturing editor.
- Length changes explicitly save only when requested; closing FreeCAD discards unsaved changes according to FreeCAD's normal behavior.
- On the tested macOS/Qt build, a crash occurred in Qt accessibility while FreeCAD animated a camera fit. The bridge avoids animated startup framing and no longer fits the desktop camera after web edits. This mitigates the observed path; it is not a general Qt crash fix.

See [architecture](docs/architecture.md) for the broader design.

This is an independent project, not an official FreeCAD product.
