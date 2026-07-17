#!/usr/bin/env python3
"""
Export student logs and artifacts as a timestamped zip file.
Run this at submission time to create a portable submission file.

Usage:
    python export.py
"""

import os
import re
import sys
import json
import platform
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Anchor all paths to this file's location, not the process cwd.
APP_DIR = Path(__file__).resolve().parent      # UI/app  (config.yaml lives here)
PROJECT_ROOT = APP_DIR.parent                    # UI      (logs/, artifacts/, and the output zip live here)

SUMMARY_SCHEMA_VERSION = 3

# Instructor-analysis-only threshold (not instructor/student form config --
# deliberately not exposed in config.yaml). Character count after .strip().
SHORT_RESPONSE_THRESHOLD = 20

LONGEST_PREVIEW_CHARS = 200

FALLBACK_SCALE_FIELDS = ["confidence", "clarity", "support"]

CHECKIN_RE = re.compile(r"^session_(?P<id>.+)_checkin\.json$")
CHECKOUT_RE = re.compile(r"^session_(?P<id>.+)_checkout\.json$")
INPUTLOG_RE = re.compile(r"^session_(?P<id>.+)_inputlog_\d+\.json$")


def get_title_slug():
    """Read the course/project title from config.yaml and slugify it for filenames."""
    if yaml is None or not (APP_DIR / "config.yaml").exists():
        return None
    with open(APP_DIR / "config.yaml") as f:
        config = yaml.safe_load(f) or {}
    title = config.get("title")
    if not title or title == "LLM Usage Logger":
        return None
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    return slug or None


# ============================================================================
# SUMMARY GENERATION (fully local, deterministic -- no LLM, no network)
# ============================================================================

def load_config():
    """Load config.yaml the same way app.py does, for field discovery. Returns {} if unavailable."""
    config_path = APP_DIR / "config.yaml"
    if yaml is None or not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fields_of_type(config, event_type, *types):
    """Field dicts from config[event_type] whose 'type' is one of `types`."""
    return [f for f in (config.get(event_type) or []) if f.get("type") in types]


def _load_json_files(logs_path, pattern):
    """Return [(Path, id, dict), ...] for every logs/ file matching a compiled regex with named group 'id'."""
    results = []
    for file in sorted(logs_path.glob("*.json")):
        m = pattern.match(file.name)
        if not m:
            continue
        try:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Skipping unreadable log file {file.name}: {e}")
            continue
        results.append((file, m.group("id"), data))
    return results


def compute_counts_and_pairs(logs_path):
    """Return (counts, pairs, checkins, checkouts, inputlogs) -- the loaded
    file-lists are reused by every metric below to avoid re-globbing."""
    checkins = _load_json_files(logs_path, CHECKIN_RE)
    checkouts = _load_json_files(logs_path, CHECKOUT_RE)
    inputlogs = _load_json_files(logs_path, INPUTLOG_RE)

    checkin_ids = {sid for _, sid, _ in checkins}
    checkout_ids = {sid for _, sid, _ in checkouts}

    counts = {
        "checkin": len(checkins),
        "inputlog": len(inputlogs),
        "checkout": len(checkouts),
        "total": len(checkins) + len(inputlogs) + len(checkouts),
    }
    pairs = {
        "complete_pairs": len(checkin_ids & checkout_ids),
        "orphaned_checkins": sorted(checkin_ids - checkout_ids),
        "orphaned_checkouts": sorted(checkout_ids - checkin_ids),
    }
    return counts, pairs, checkins, checkouts, inputlogs


def compute_input_metrics(inputlogs):
    """inputlogs: list of (Path, session_id, data) for inputlog files."""
    if not inputlogs:
        return {
            "avg_inputs_per_inputlog": None,
            "avg_inputs_per_session": None,
            "inputlog_file_count": 0,
            "session_count_with_inputlogs": 0,
            "longest_input": None,
        }

    per_file_counts = []
    per_session_counts = {}
    longest = None  # (length, value, filename, input_index)

    for file, sid, data in inputlogs:
        entries = data.get("inputs") or []
        input_entries = [p for p in entries if p.get("type") == "input"]
        n = len(input_entries)
        per_file_counts.append(n)
        per_session_counts[sid] = per_session_counts.get(sid, 0) + n

        for p in input_entries:
            text = p.get("text") or ""
            if longest is None or len(text) > longest[0]:
                longest = (len(text), text, file.name, p.get("index"))

    avg_per_file = sum(per_file_counts) / len(per_file_counts)
    avg_per_session = (
        sum(per_session_counts.values()) / len(per_session_counts)
        if per_session_counts else None
    )

    longest_input = None
    if longest is not None:
        length, value, fname, idx = longest
        longest_input = {
            "value": value,
            "length": length,
            "source_file": fname,
            "input_index": idx,
        }

    return {
        "avg_inputs_per_inputlog": round(avg_per_file, 2),
        "avg_inputs_per_session": round(avg_per_session, 2) if avg_per_session is not None else None,
        "inputlog_file_count": len(inputlogs),
        "session_count_with_inputlogs": len(per_session_counts),
        "longest_input": longest_input,
    }


def compute_scale_averages(config, checkouts):
    """Returns (result_dict, used_fallback). Field names come from config.yaml
    (never hardcoded) unless config.yaml itself is unavailable."""
    scale_fields = [f["field"] for f in fields_of_type(config, "checkout", "scale_1_5")]
    used_fallback = False
    if not scale_fields:
        scale_fields = FALLBACK_SCALE_FIELDS
        used_fallback = True

    result = {}
    for field_name in scale_fields:
        values = []
        for _, _, data in checkouts:
            raw = data.get(field_name)
            if raw is None or raw == "":
                continue
            try:
                values.append(int(raw))
            except (TypeError, ValueError):
                continue
        result[field_name] = {
            "average": round(sum(values) / len(values), 2) if values else None,
            "count_answered": len(values),
            "count_total_checkouts": len(checkouts),
        }
    return result, used_fallback


def compute_short_responses(config, checkins, inputlogs, checkouts):
    """Config-driven scan of every text/textarea field across all three event types."""
    by_field = {}
    total_short = 0

    def scan(event_type, files):
        nonlocal total_short
        text_fields = [f["field"] for f in fields_of_type(config, event_type, "text", "textarea")]
        for field_name in text_fields:
            key = f"{event_type}.{field_name}"
            short_count = 0
            for _, _, data in files:
                value = data.get(field_name)
                if value is None:
                    continue
                if len(str(value).strip()) < SHORT_RESPONSE_THRESHOLD:
                    short_count += 1
            by_field[key] = short_count
            total_short += short_count

    scan("checkin", checkins)
    scan("inputlog", inputlogs)
    scan("checkout", checkouts)

    return {
        "threshold_chars": SHORT_RESPONSE_THRESHOLD,
        "by_field": by_field,
        "total_short": total_short,
    }


def compute_longest_entries(config, checkins, inputlogs, checkouts):
    """Longest value per field name, plus a specifically-called-out longest
    reflection (which spans three separate fields)."""
    by_field = {}

    def scan(event_type, files):
        text_fields = [f["field"] for f in fields_of_type(config, event_type, "text", "textarea")]
        for field_name in text_fields:
            key = f"{event_type}.{field_name}"
            best = None
            for path, _, data in files:
                value = data.get(field_name)
                if not value:
                    continue
                value = str(value)
                if best is None or len(value) > best[0]:
                    best = (len(value), value, path.name)
            if best is not None:
                length, value, fname = best
                by_field[key] = {"value": value, "length": length, "source_file": fname}

    scan("checkin", checkins)
    scan("inputlog", inputlogs)
    scan("checkout", checkouts)

    longest_reflection = None
    for path, _, data in inputlogs:
        combined = " ".join(
            str(data.get(k) or "") for k in
            ("reflection_outcome", "reflection_errors", "reflection_surprises")
        ).strip()
        if not combined:
            continue
        if longest_reflection is None or len(combined) > longest_reflection[0]:
            longest_reflection = (len(combined), combined, path.name)

    longest_reflection_out = None
    if longest_reflection is not None:
        length, value, fname = longest_reflection
        longest_reflection_out = {"value": value, "length": length, "source_file": fname}

    return {"by_field": by_field, "longest_reflection": longest_reflection_out}


def generate_summary():
    """Compute the full analysis summary dict from logs/. Returns the summary dict."""
    logs_path = PROJECT_ROOT / "logs"
    config = load_config()

    counts, pairs, checkins, checkouts, inputlogs = compute_counts_and_pairs(logs_path)
    input_metrics = compute_input_metrics(inputlogs)
    scale_averages, used_fallback = compute_scale_averages(config, checkouts)
    short_responses = compute_short_responses(config, checkins, inputlogs, checkouts)
    longest_entries = compute_longest_entries(config, checkins, inputlogs, checkouts)

    course_title = config.get("title") or "LLM Usage Logger"

    caveats = [
        "Abandoned/incomplete input logs (started but never finished via Finish & Reflect) "
        "are not saved to disk and cannot be counted from exported files.",
        "Check-in/check-out pairing uses exact session_id match only; the app assigns "
        "session_id per app-launch, not per logical work session, so a restart between "
        "check-in and check-out produces an unmatched pair even for a continuous work session.",
    ]
    if used_fallback:
        caveats.append(
            "config.yaml's checkout scale_1_5 fields could not be discovered "
            f"(using fallback field names {FALLBACK_SCALE_FIELDS}); scale averages "
            "may not reflect this class's actual configured fields."
        )

    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(),
        "course_title": course_title,
        "counts": counts,
        "session_pairs": pairs,
        "inputs": input_metrics,
        "scale_averages": scale_averages,
        "short_responses": short_responses,
        "longest_entries": longest_entries,
        "caveats": caveats,
    }
    return summary


def render_summary_markdown(summary):
    """Human-readable rendering: skimmable top-to-bottom in under a minute.
    Most "is something wrong" signal first, numbers before prose, longest
    entries last (interesting but not urgent)."""
    lines = []
    lines.append(f"# Submission Summary -- {summary['course_title']}")
    lines.append(f"_Generated {summary['generated_at']} | schema v{summary['schema_version']}_")
    lines.append("")

    c = summary["counts"]
    lines.append("## Log Counts")
    lines.append(f"- Check-ins: **{c['checkin']}**")
    lines.append(f"- Process logs: **{c['inputlog']}**")
    lines.append(f"- Check-outs: **{c['checkout']}**")
    lines.append(f"- Total: **{c['total']}**")
    lines.append("")

    p = summary["session_pairs"]
    lines.append("## Session Pairing (exact session_id match)")
    lines.append(f"- Complete check-in/check-out pairs: **{p['complete_pairs']}**")
    if p["orphaned_checkins"]:
        lines.append(f"- Check-ins with no matching check-out: {', '.join(p['orphaned_checkins'])}")
    if p["orphaned_checkouts"]:
        lines.append(f"- Check-outs with no matching check-in: {', '.join(p['orphaned_checkouts'])}")
    lines.append("")

    im = summary["inputs"]
    lines.append("## Input Activity")
    if im["inputlog_file_count"] == 0:
        lines.append("- No process logs recorded.")
    else:
        lines.append(f"- Avg inputs per process log: **{im['avg_inputs_per_inputlog']}**")
        lines.append(f"- Avg inputs per session: **{im['avg_inputs_per_session']}**")
        lines.append(f"- Sessions with at least one process log: {im['session_count_with_inputlogs']}")
    lines.append("")

    lines.append("## Self-Reported Scales (checkout)")
    for field, stats in summary["scale_averages"].items():
        avg = stats["average"]
        avg_str = f"{avg}" if avg is not None else "N/A"
        lines.append(f"- {field}: avg **{avg_str}** ({stats['count_answered']}/{stats['count_total_checkouts']} answered)")
    lines.append("")

    sr = summary["short_responses"]
    lines.append(f"## Short Responses (< {sr['threshold_chars']} chars)")
    lines.append(f"- Total short entries: **{sr['total_short']}**")
    for field, n in sr["by_field"].items():
        if n:
            lines.append(f"  - {field}: {n}")
    lines.append("")

    le = summary["longest_entries"]
    lines.append("## Longest Entries (per field)")
    for field, entry in le["by_field"].items():
        preview = entry["value"][:LONGEST_PREVIEW_CHARS]
        suffix = f"... [truncated, {entry['length']} chars total]" if entry["length"] > LONGEST_PREVIEW_CHARS else ""
        lines.append(f"- **{field}** ({entry['length']} chars, {entry['source_file']}): {preview}{suffix}")
    if le["longest_reflection"]:
        r = le["longest_reflection"]
        preview = r["value"][:LONGEST_PREVIEW_CHARS]
        suffix = f"... [truncated, {r['length']} chars total]" if r["length"] > LONGEST_PREVIEW_CHARS else ""
        lines.append("")
        lines.append(f"**Longest reflection overall** ({r['length']} chars, {r['source_file']}): {preview}{suffix}")
    lines.append("")

    lines.append("## Notes")
    for note in summary["caveats"]:
        lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


# ============================================================================
# EXPORT (zip creation)
# ============================================================================

def export_submission():
    """Create a zip file with logs, artifacts, and an embedded summary. Returns the zip Path on success, or None on failure."""

    logs_path = PROJECT_ROOT / "logs"
    artifacts_path = PROJECT_ROOT / "artifacts"

    if not logs_path.exists():
        print("[ERROR] 'logs' directory not found")
        print("  Run the app at least once before exporting.")
        return None

    # Create zip filename with timestamp, prefixed with the course title if set
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = get_title_slug()
    zip_filename = f"submission_{slug}_{timestamp}.zip" if slug else f"submission_{timestamp}.zip"
    zip_path = PROJECT_ROOT / zip_filename

    # Summary generation is best-effort: a bug in the new analysis code must
    # never block a student's ability to export their actual graded work.
    try:
        summary = generate_summary()
        summary_json_text = json.dumps(summary, indent=2)
        summary_md_text = render_summary_markdown(summary)
    except Exception as e:
        print(f"[WARN] Summary generation failed, exporting without it: {e}")
        summary_json_text = None
        summary_md_text = None

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all files from logs directory
            if logs_path.exists():
                for file in logs_path.glob("*"):
                    if file.is_file():
                        zipf.write(file, arcname=f"logs/{file.name}")

            # Add all files from artifacts directory
            if artifacts_path.exists():
                for file in artifacts_path.rglob("*"):
                    if file.is_file():
                        rel_path = file.relative_to(artifacts_path)
                        zipf.write(file, arcname=f"artifacts/{rel_path}")

            # Embed the summary alongside logs/ and artifacts/ as a sibling folder
            if summary_json_text is not None:
                zipf.writestr("summary/summary.json", summary_json_text)
                zipf.writestr("summary/summary.md", summary_md_text)

        print(f"[OK] Export successful!")
        print(f"  File: {zip_filename}")
        print(f"  Size: {zip_path.stat().st_size / 1024:.1f} KB")
        print(f"\nYou can now submit '{zip_filename}' to the course portal.")
        return zip_path

    except Exception as e:
        print(f"[ERROR] Export failed: {e}")
        return None

def show_message_box(message, title, icon=0x40):
    """Best-effort native dialog for headless (no-console) launches.
    icon: 0x40 = info (success), 0x10 = error. Mirrors start.py's show_error_box."""
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, icon)
        except Exception:
            pass

if __name__ == "__main__":
    # Under pythonw.exe (used by Export.vbs for a windowless launch) there
    # is no console, so sys.stdout/stderr are None. Redirect to the same
    # launch_log.txt used by start.py so print() doesn't crash and output
    # is still recoverable, and so both tools share one log file.
    headless = sys.stdout is None
    if headless:
        log_file = open(APP_DIR / "launch_log.txt", "a", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"\n--- Export attempt at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    zip_path = export_submission()

    if headless:
        if zip_path:
            show_message_box(
                f"Export successful!\n\n"
                f"Created: {zip_path.name}\n"
                f"Location: {zip_path.parent}\n\n"
                f"Upload this zip file to the course portal.",
                "LLM Usage Logger - Export Complete",
                icon=0x40,
            )
        else:
            show_message_box(
                f"Export failed.\n\n"
                f"See launch_log.txt in the app folder for details.\n\n"
                f"Common cause: you haven't started the app yet. Run Start.vbs "
                f"first, use the app, then export.",
                "LLM Usage Logger - Export Failed",
                icon=0x10,
            )

    sys.exit(0 if zip_path else 1)
