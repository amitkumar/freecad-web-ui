# Prototype 01 implementation

The first version uses plain JavaScript ES modules with Three.js and a Python standard-library HTTP server inside FreeCAD. TypeScript and WebSockets remain possible later improvements; neither is required for the first milestone.

- `bridge/StartWebUI.FCMacro`: manual FreeCAD entry point.
- `bridge/freecad_web_bridge.py`: local server, main-thread queue, sample document, mesh export, revision handling, and save.
- `bridge/protocol.py`: isolated validation rules.
- `web/`: browser interface, camera controls, authoritative mesh display, length form, and connection/save status.
- `tests/`: protocol unit tests, opt-in HTTP integration checks, and a FreeCAD-side smoke macro.

API:

- `GET /api/snapshot`: session, revision, authoritative dimensions, saved status, and tessellated geometry.
- `POST /api/command`: `set_length` or `save`, with session, expected revision, and request ID.

Both require the session's bearer token. Every request validates the loopback Host and any Origin header. Static files are served from an explicit list; local-data and source files are never served.

The HTTP worker threads enqueue operations. A retained Qt timer processes them on the FreeCAD application thread with a reentrancy guard. The cache retains 128 command results, including failures. Duplicate IDs with different request bodies are rejected. Commands waiting in the queue expire after eight seconds; a timeout during execution may be ambiguous, so clients refresh rather than silently retry.

Revision changes are detected by polling a fingerprint of board dimensions and placement. The saved geometry fingerprint is read from the actual FCStd archive when the file changes. File contents, not browser state, determine persistence status.

An interrupted connection disables edits. A new session is authorized by rerunning the macro and reopening its link. The browser retains the token in localStorage for this exact origin, with sessionStorage as a fallback. Tabs reread shared authorization while polling so a tab waiting for authorization can recover once another tab opens the authorized link. A stale credential produces an authorization-needed message rather than implying FreeCAD stopped. The current prototype is local-only and intentionally has no deployment configuration.
