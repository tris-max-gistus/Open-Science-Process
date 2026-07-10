# Iterating On This Tool's Design

If you're curious about changing this tool for your own purposes — a different kind of process log, a new feature, a different set of questions — this file gives an AI assistant enough context to help you design it. Fill in your ideas below, then paste this **whole file** into an AI chat (like Claude) to start ideating.

**Before you fork and start changing things:** see `versioning_with_github.md` in this folder for how to make and track your own copy.

**Submissions are in the provided version.** Whatever you build here is for your own exploration — it is not what you turn in for the class. Your actual submission always comes from the unmodified version your instructor gave you, exported the normal way. Treat this as a personal sandbox, not a replacement for your official logs.

------------------------------------------------------------
MY IDEAS (fill this in)

What do you want to change or add?


Why does this matter to you? What would make this tool more useful for your own work?


Is this about the questions being asked (config.yaml), the process log flow itself, a new feature, or something else entirely?


------------------------------------------------------------
CONTEXT FOR THE AI HELPING ME (leave this part as-is)

This is a local Flask web app for logging a student's project process and AI usage, structured around three events per work session: Check-In, Process Log, Check-Out. It's fully local — no network calls, no LLM integration, nothing leaves the student's machine.

**Folder structure:**
```
/               top level: launchers (Start.vbs/start.command), README, help/, artifacts/, logs/
/app            all internals: app.py (Flask server), config.yaml, export.py, start.py, venv/
/logs           JSON files, one per Check-In/Process Log/Check-Out submission
/artifacts      free-form files students add themselves, plus artifacts/process-log/ (AI outputs flagged during a session)
```

**Everything question-related is config-driven.** `app/config.yaml` defines every form field across four sections (`checkin`, `promptlog`, `checkout`, `artifact`), each field having a stable internal `field` name, a `label` (the question shown to the user), a `type` (`text`/`textarea`/`scale_1_5`, plus a few special types used only by the Process Log screen), and a `placeholder`. `app.py` renders forms directly from this file — changing a question's wording never requires touching Python code.

**Session flow:**
- Check-In (`/api/checkin`) — one-time fields at the start of a session.
- Process Log (`/api/promptlog/start`, `/api/promptlog/add-prompt`, `/api/promptlog/add-note`, `/api/promptlog-reflection`) — one log covers a whole work block. Prompts and notes are independently-submitted, equally-weighted entries in one interleaved list (prompts numbered, notes marked `-`), closed out with a three-question reflection.
- An **Artifacts** flow (`/api/promptlog/artifact`) lets a student save an especially helpful or problematic AI response as a plain `.txt` file in `artifacts/process-log/` — this is the one place in the tool where AI output itself is ever saved; everywhere else only records what the student typed.
- Check-Out (`/api/checkout`) — closing fields, including three 1-5 self-report scales.

**Every saved JSON file is a flat, timestamped record** — `session_<id>_checkin.json`, `session_<id>_promptlog_<n>.json`, `session_<id>_checkout.json` — written to `/logs`. No student-identifying information is collected anywhere; that linkage happens externally, through a course's own submission system.

**Export** (`app/export.py`) zips `/logs` and `/artifacts` into one timestamped file, and also computes a local, fully deterministic analytics summary (counts, averages, longest entries) embedded in the zip — no AI or network calls involved in that either.

------------------------------------------------------------
Copy this whole file (with your ideas filled in above) and paste it into an AI chat to start designing your change.
