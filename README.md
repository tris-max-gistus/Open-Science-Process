# Process Logger

A simple tool to log your process as part of this course's educational research study on systems thinking, ethical generative artificial intelligence, and open science documentatin.

## Important: This is NOT evaulated against a rubric

Your usage of AI tools is **not** judged or graded based on the patterns in this log. We're studying how students engage with AI to understand learning processes, not to enforce policies. Be honest about your process.

## Privacy & Data

- **No personal identifying information** is collected by this tool (no name, ID number, email, etc.)
- **All data stays on your computer** until you choose to export and submit it
- **Linkage to your identity** happens through your course's existing submission portal, not through this tool

## Quick Start

### First Time Setup (Instructor)
1. Extract this folder
2. Open `app/config.yaml` and set `title:` to your course or project name (helpful if you're running this tool for more than one class)
3. **Windows:** double-click `Start.vbs` (no console window; only pops up a small message if something goes wrong). **Mac:** double-click `start.command` (first time only, you may need to right-click it and choose Open). If double-clicking doesn't work on your machine, open a terminal in this folder and run `python app/start.py` instead.
4. A browser window will open automatically at `http://localhost:5000`, titled with whatever you set in step 2

If you want a desktop shortcut, point it at `Start.vbs` for a clean, no-console launch. If something ever seems stuck or broken, run `app/start.bat` once instead — the visible output usually explains what's wrong (and `Start.vbs` also logs to `app/launch_log.txt` either way).

If you're using this tool for multiple classes, keep a separate copy of this whole folder per class (each gets its own `config.yaml` title, logs, and data — nothing is shared between them).

### During Your Work Session

Right below the title, a small box shows **Last time** (what you said your next session should start with) and **Today** (what you just entered as today's goal, once you've checked in). It's there so you can pick up your train of thought before you dive back in — especially useful if this session is on a completely different part of the project than last time.

The main page has three buttons:

**Session Check-In**
- Fill this out once at the **start** of each work session
- Questions: project stage, goal for today, planned time, system state
- If you answered "what should next session start with?" at your last check-out, that answer will already be filled into the goal field — edit it or leave it as-is

**Process Log**
- You do **not** check in for every individual prompt — one log covers a whole process work block
- Click the button once to start a log: explain your intent and your own prediction of the approach/output
- As you work, add each note you would like to document about the process and prompt you send to the AI one at a time — the log keeps a running, numbered list so you can see how many you've logged
- The button on the main screen shows a live count while a log is open, so you always know it's still active
- When the block is done, click "Finish & Reflect" to answer the reflection question and close the log out
- If you click "Process Log" again without finishing, it reopens the same in-progress log — nothing is lost, but it also won't save until you explicitly finish it

**Session Check-Out**
- Fill this out once at the **end** of each session
- Questions: time spent, what you built, surprises, next steps, confidence scales

## File Structure

```
/logs              → All your session logs (JSON files)
/artifacts         → Manually add any code, designs, or work here
/help              → Troubleshooting, versioning, and idea-starter docs
/app               → Internal files (server code, config, launcher scripts) — you shouldn't need to open this
Start.vbs          → Windows double-click launcher (no console window) — start here
Export.vbs         → Windows double-click launcher — creates your submission zip
start.command      → Mac double-click launcher — start here
export.command     → Mac double-click launcher — creates your submission zip
```

If you're curious, everything the app needs to run — `config.yaml`, the server code, the Python virtual environment — lives inside `/app`. You don't need to go in there for normal use.

## Submitting Your Work

When you're ready to submit (at deadline):

1. **Windows:** double-click `Export.vbs`. **Mac:** double-click `export.command`. (If double-clicking doesn't work, open a terminal in this folder and run `python app/export.py` instead.)
2. A confirmation window (Windows) or Terminal message (Mac) will tell you the zip file was created, and where.
3. The zip file (e.g., `submission_20250101_120000.zip`) appears at the top level of this folder — upload that file to the course portal.

The zip file contains your `/logs` and `/artifacts` — nothing else.

## FAQ

**Can I use this on multiple devices?**
The tool is designed for one student on one device. If you work on different computers, you'll have separate logs — export each one and note which device it's from.

**What if I make a mistake in a log?**
You can manually edit JSON files in the `/logs` folder if needed. Each log is a plain text JSON file.

**What if I want to start fresh?**
Delete the `/logs` folder and the tool will create a fresh session on next run. The `/artifacts` folder is for you to manage.

**Is this tool open source?**
Yes, you're welcome to explore the code and modify it for your own needs after the course.

---

**Questions?** Check with your instructor. This tool is here to help you reflect on your process, not police your AI use.
