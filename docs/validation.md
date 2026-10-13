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
