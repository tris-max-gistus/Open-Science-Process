# Troubleshooting

Known issues and fixes, newest additions at the top. Each entry follows
the same format — see "Adding a new entry" at the bottom.

---

## Folder still won't move, even though no python process is running

**Symptom:** `Get-Process python,pythonw` (see the entry below) shows
nothing, but moving/renaming the folder still fails with "The process
cannot access the file because it is being used by another process."

**Cause:** A freshly-created `app/venv/` contains real executables
(`python.exe`, DLLs). Something else — usually antivirus scanning those
new binaries, sometimes the search indexer — can hold a brief lock on
them that has nothing to do with the app itself. See
`venv_architecture.md` for why this folder structure makes that possible
and how to avoid it.

**Fix:** Delete the `app/venv/` subfolder (it's disposable — the launcher
rebuilds it automatically), then move the folder. Don't try to move a
`venv/` folder directly even if you do get it unstuck — it embeds
absolute paths and isn't portable anyway.

---

## "It says the app is already running" / can't move or delete the folder

**Symptom:** You get an error like "The action can't be completed because
the file is open in another program" when trying to move, rename, or
delete the project folder. Or the app fails to start with a "Port 5000
is already in use" message — even though you already closed the browser
tab.

**Cause:** Closing the browser tab doesn't always fully stop the local
server. The app's Python process can keep running in the background,
which locks the folder (Windows won't let you move/rename a folder that
contains a currently-running program) and keeps port 5000 occupied.

**Fix:** find that process and stop it.

**Windows (PowerShell)** — recommended, shows exactly which folder each
process belongs to, so you can be sure you're stopping the right one:
```
Get-Process python,pythonw -ErrorAction SilentlyContinue | Select-Object Id, Path
```
Find the row whose Path is inside this project's folder, then:
```
Stop-Process -Id <id> -Force
```

**Windows (Command Prompt)** — alternative, based on the port instead:
```
netstat -ano | findstr :5000
taskkill /PID <pid> /F
```

**Mac/Linux:**
```
lsof -i :5000
kill -9 <pid>
```

Then try the original action again.

---

## Adding a new entry

Copy this template and fill it in:

```
## Short description of the error

**Symptom:** What you see (exact error text if possible).

**Cause:** Why it happens, if known.

**Fix:** Steps to resolve it.
```

Add new entries above this section, so the newest is always closest to
the top.
