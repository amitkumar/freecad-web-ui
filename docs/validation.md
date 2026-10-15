# Prototype validation

Verified on macOS with FreeCAD 1.1.4 and Chrome, October 13, 2026:

- Browser rendered live FreeCAD tessellation with orbit/zoom and standard camera controls.
- Browser length changes updated the real FreeCAD Part::Box, including a final independently checked 20 in / 508 mm value.
- Explicit browser Save wrote the geometry to the FCStd file.
- After an interrupted FreeCAD session, rerunning the macro reopened the previously saved 18-inch board correctly and authorized a new browser session.
- Six protocol unit tests and two opt-in live integration tests passed.
- Live checks covered authorization, origin/host validation, private-file isolation, invalid values, stale revisions, duplicate request IDs, mesh dimensions, and saved FCStd XML values.
- JavaScript syntax and Git whitespace checks passed.
- CAD models, session links, and installed dependencies are ignored by Git.

A macOS crash occurred during testing. The stack showed Qt accessibility object destruction while FreeCAD ran an animated camera-fit event loop. Startup now frames without animation; web edits no longer fit the desktop camera; a reentrancy guard protects the main-thread request queue. Subsequent HTTP integration and browser edit/save checks passed. These changes mitigate the observed code path, not all potential Qt/macOS crashes.

`tests/FreeCADSmoke.FCMacro` is provided for direct-edit observation, undo/redo, and an explicit save/close/reopen cycle. It was not executed successfully during this session because native file-dialog automation became unreliable. Those additional checks remain unverified; they are not included in the passing test count.


## Isolated launcher checks — October 14, 2026

- Six launcher tests passed, covering dedicated paths/environment, refusal while FreeCAD is running, refusal on an occupied port, preservation of config/recovery files, initial animation settings, and failure when process detection is unavailable. Execution of FreeCAD was mocked.
- Six existing protocol tests passed; the two opt-in live tests were skipped.
- Shell syntax and Python/macro syntax checks passed.
- A real `--dry-run` detected an existing FreeCAD process and reported the blocker without starting/stopping a process or creating runtime files.
- The complete isolated GUI launch and FreeCAD-side smoke macro remain unverified pending a coordinated session handoff. The earlier stable prototype commit remains independently usable.


## Coordinated full test — October 14, 2026

The earlier pending native checks are now verified for an isolated synthetic-board session on FreeCAD 1.1.4/macOS. Main reserved a tooling-only process window. The test copied only public tooling code into a temporary directory, used its own board/config/recovery, and did not control the existing user's FreeCAD GUI or open apartment documents.

- The launch routine directly executed a tracked FreeCAD child. Its report confirmed `QT_ACCESSIBILITY=0`, the dedicated recovery path, and the intended synthetic document.
- The temporary harness explicitly substituted only the running-FreeCAD check under the approved sibling-process test reservation. Port, checkout lock, settings and recovery checks remained active. The normal public launcher continues refusing existing FreeCAD processes; its refusal was separately verified.
- The native smoke macro passed direct-edit observation, stale-command rejection, undo, redo, restoration, save, close, reopen, valid solid and saved-state comparison. The initial 14-inch value persisted through the native reopen.
- All 14 automated tests passed, including both opt-in live API tests.
- Chrome displayed the child's geometry, changed length from 14 to 18 inches, and saved it. Independent FCStd XML inspection confirmed 457.2 mm.
- A test-harness-only local shutdown watcher verified sole-document identity, saved and closed the synthetic document, stopped the bridge, and closed its own window. The tracked child exited with status 0; no process was force-terminated. This shutdown watcher is not part of the public bridge API.

Local evidence includes launch/smoke/shutdown JSON reports and the saved browser screenshot. Session credentials, temporary runtime files and apartment data are excluded from public source. These results establish the tested workflow, not a general Qt/macOS crash fix or long-duration stability guarantee.
