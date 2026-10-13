# FreeCAD Web UI

A local WebGL interface for reviewing and making controlled edits to a FreeCAD model, with FreeCAD remaining the single source of truth.

## Status

Planning scaffold. No web viewer or live bridge is implemented yet.

## Intended workflow

```text
Browser UI <-> local bridge <-> active FreeCAD document
                   |
                   +-> generated display geometry and object metadata -> Browser UI
```

The browser displays derived geometry and sends structured commands. FreeCAD owns design geometry, parameters, placements, recomputation, undo, and persistence. Browser meshes are disposable display data, never an independent editable design.

## Proposed stack

- TypeScript and Three.js for the browser interface and WebGL rendering.
- A Python integration running inside the user's installed FreeCAD application.
- A local HTTP/WebSocket transport, with its implementation chosen during the prototype.
- Generated mesh data and metadata identifying objects, dimensions, units, and model revision.

## First milestone

Use a synthetic rectangular board to prove the complete connection:

1. Open the board in FreeCAD.
2. Display its geometry and dimensions in the browser.
3. Change its length through an explicitly allowed browser control.
4. Apply the change in FreeCAD, recompute, and report errors.
5. Refresh the browser from the resulting FreeCAD state.
6. Save in FreeCAD, reopen, and verify the same dimension persists.

## Planned features

- Orbit, pan, zoom, standard views, and saved viewpoints.
- Object selection, visibility toggles, and authoritative property inspection.
- Model revision, connection status, and saved/unsaved indicators.
- Controlled parameter and placement edits with undo support.
- Apartment walkthrough controls after the review workflow works reliably.

General sketch editing and arbitrary face/edge operations are outside the initial scope.

## Design rules

- One active document owner; do not write a second process's stale copy over a document open in FreeCAD.
- Route document operations onto FreeCAD's application thread.
- Reject stale edit commands and validate allowed object/property/value combinations.
- Roll back failed edits and show recomputation errors.
- Distinguish a successful in-memory change from a successful save.
- Preserve object identity independently of display labels and tessellation indices.
- Keep units explicit across the bridge.
- Restrict the bridge to loopback with session authorization and origin checks; do not expose arbitrary Python execution or unrestricted file access.
- Keep private CAD projects, apartment measurements, credentials, and generated previews out of this public repository.

See [architecture](docs/architecture.md) for implementation considerations.

## Development

There are no installation or launch commands yet. The first implementation should establish and test the FreeCAD bridge before expanding the interface.

This is an independent project, not an official FreeCAD product.
