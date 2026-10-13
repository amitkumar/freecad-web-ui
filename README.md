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

The server runs inside FreeCAD at `http://127.0.0.1:8765/`. Keep FreeCAD running. The authorized viewer link is also stored in ignored `local-data/viewer-url.txt`; treat it as a local credential. A plain link requires an already-authorized browser tab session.

If FreeCAD restarts, execute the macro again and use the newly opened viewer. If port 8765 is already occupied by another application, startup fails rather than selecting an unexpected address. Re-executing the macro replaces its previous bridge session.

To stop the bridge without quitting FreeCAD, run this in FreeCAD's Python console:

```python
App._web_ui_bridge.stop()
```

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
