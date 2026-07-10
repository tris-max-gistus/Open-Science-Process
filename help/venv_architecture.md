# Venv Architecture

Each copy of this app folder is fully self-contained: `app/start.py`
creates and uses a `venv/` subfolder relative to its own location (i.e.
`app/venv/`), independent of every other copy. Duplicate `UI` into
`Math` and `Physics`, and you get two completely separate runtimes —
nothing shared, nothing that can cross-contaminate between them.

## Why

- **Isolation.** One copy's venv breaking (corruption, a stray pip
  install) can't affect any other copy.
- **Self-containment.** A folder is a complete, working instance on its
  own — no external dependency to track or keep in sync.
- **Standard practice.** Same pattern as `node_modules` per JS project:
  per-project environments beat one shared global one, specifically
  because it prevents cross-project coupling.
- **Cheap.** This venv is just Flask + PyYAML — tens of MB. Duplicating
  it per class costs nothing meaningful.

## The practical rule

`app/venv/` is disposable and fully regenerable — `start.py` rebuilds
it from nothing on first run. It is **not portable**: a freshly-built
venv's executables can transiently lock (usually antivirus scanning
new binaries), which can block moving the folder that contains it.

**Before moving, archiving, or duplicating a class folder:**
1. Delete its `app/venv/` subfolder
2. Move / copy / zip freely — the folder is now just plain files
3. Run the launcher once in the new location — `app/venv/` rebuilds
   automatically

Treat `app/venv/` like a build artifact, never like part of the folder's
real content.
