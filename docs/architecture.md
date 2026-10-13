# Architecture proposal

This document describes intended behavior, not an implemented API.

## Authority and state

The active FreeCAD document is authoritative for committed model changes. Its saved FCStd file persists that state. Browser camera position, selection, and temporary visibility choices may remain local to the viewer unless explicitly promoted into model properties.

Maintain a document-session identifier and monotonically increasing revision for accepted changes. A browser command carries the session, expected revision, request identifier, target object identity, operation, and typed values. Changing documents invalidates the previous session. Revision tracking must also observe desktop edits, undo, and redo; browser commands are not the only source of changes.

Separate model revision from export revision so the browser can identify a stale display while tessellation is pending. Snapshots must correspond to one coherent model revision. Reconnection retrieves a fresh snapshot rather than replaying uncertain changes.

## Command handling

1. Authenticate the local client and validate its origin.
2. Validate the command against a narrow operation allowlist.
3. Schedule processing on FreeCAD's application thread.
4. Verify document identity and expected revision.
5. Open a document transaction, apply the change, and recompute.
6. Check affected object states and geometry where applicable; abort on failure.
7. Commit on success, advance the revision, and publish the authoritative result.
8. Refresh affected display data. Saving is an explicit operation with its own success/failure result.

Use request identifiers to avoid applying duplicate commands after retries. Serialize edits; do not mutate the document from network worker threads.

## Display export

Tessellate FreeCAD geometry for WebGL rather than attempting to manipulate the CAD boundary representation in the browser. Package object identities, placements, units, dimensions, and display geometry. Choose the mesh transport after a small export benchmark; GLB is a candidate, not a required native FreeCAD export capability.

Property inspection should use FreeCAD values. Mesh-derived measurements, if added, must be labeled approximate. Initially export complete snapshots; incremental updates can follow once correctness is established.

## Local boundary

The initial target is one user, one local FreeCAD instance, and a browser on the same computer. Loopback binding alone is insufficient: require a per-session secret, validate origins, avoid wildcard CORS, and expose only structured operations. Keep dependencies and static assets local at runtime where practical.

Remote access, multiuser editing, arbitrary Python evaluation, and full CAD editing are outside the initial scope.

## Validation milestones

- Synthetic board geometry is displayed with correct dimensions and orientation.
- Browser length edit updates the FreeCAD document and viewer.
- Desktop edits invalidate stale browser revisions.
- Invalid changes roll back; duplicate requests do not apply twice.
- Undo and redo refresh browser state.
- Saving and reopening preserves the intended dimension.
- Disconnect and reconnect recover authoritative state.
- Unauthorized origins and missing session authorization are rejected.
