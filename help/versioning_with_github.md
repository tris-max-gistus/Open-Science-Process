# Versioning This Tool With GitHub

This tool is [open source](https://github.com/tris-max-gistus/Open-Science-Process) — you're welcome to make your own copy and change it however you like, for your own purposes. This guide walks through how, using GitHub, even if you've never used it before.

**Quick reminder:** your own modified copy is for your own exploration. Whatever you submit for the actual class assignment is always the unmodified version your instructor gave you — see `ideation_prompt.md` in this folder for more on that distinction.

## Why bother with version control?

If you start changing `config.yaml` or the code and something breaks, version control lets you see exactly what you changed and undo it. It also means you can experiment freely — try something, and if it doesn't work, go back to before you tried it, no harm done.

## Option A: GitHub Desktop (no command line needed)

If you'd rather not use a terminal at all:
1. Install [GitHub Desktop](https://desktop.github.com/) and sign in with a GitHub account (free to create if you don't have one).
2. Go to the [project page on GitHub](https://github.com/tris-max-gistus/Open-Science-Process) and click **Fork** (top right) — this makes your own copy under your account.
3. In GitHub Desktop: **File → Clone Repository**, choose your fork, pick a folder on your computer.
4. Make changes to the files in that folder as you normally would.
5. Back in GitHub Desktop, you'll see your changed files listed. Write a short summary of what you changed, click **Commit to main**, then click **Push origin** to save it to your fork on GitHub.

That's the whole loop: change something → commit → push. Repeat as often as you like.

## Option B: Command line (git)

If you're comfortable with a terminal:

1. **Fork the repo** — go to the [project page](https://github.com/tris-max-gistus/Open-Science-Process), click **Fork** (top right).
2. **Clone your fork** to your computer:
   ```
   git clone https://github.com/YOUR-USERNAME/Open-Science-Process.git
   cd Open-Science-Process
   ```
3. **Make your changes** — edit `app/config.yaml`, `app/app.py`, or anything else.
4. **Save a checkpoint** of your changes:
   ```
   git add .
   git commit -m "describe what you changed here"
   ```
5. **Push it to your fork on GitHub:**
   ```
   git push
   ```

Repeat steps 3-5 as you go. Each commit is a checkpoint you can always come back to (`git log` shows your history; `git checkout <commit>` can restore an old version if you need it).

## What NOT to commit

Some files are already excluded via `.gitignore` because they're either local-machine-specific or contain real data:
- `app/venv/` — the Python environment (regenerated automatically, never move or commit it)
- `logs/` — your actual session logs
- `artifacts/` — anything you've dropped in there
- `app/next_hint.json`, `app/launch_log.txt` — local runtime state

If you ever see git wanting to add one of these, don't force it — the `.gitignore` is there on purpose.

## Keeping your fork in sync with updates

If the original project gets updated later and you want those changes too:
```
git remote add upstream https://github.com/tris-max-gistus/Open-Science-Process.git
git fetch upstream
git merge upstream/main
```
You only need to add the `upstream` remote once; after that, `git fetch upstream` + `git merge upstream/main` whenever you want to pull in updates.

---

**Questions?** See `help/ask_for_help.txt` for the general "paste this into an AI chat" troubleshooting template — it works for git questions too, just describe what you're trying to do.
