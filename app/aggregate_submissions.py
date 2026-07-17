#!/usr/bin/env python3
"""
Aggregate per-submission summaries across many exported submission zips into
one combined spreadsheet-friendly report.

Standalone tool -- run manually against a folder of raw submission zips as
received from students. Not wired into the Flask app or any launcher.

Usage:
    python aggregate_submissions.py /path/to/folder/of/zips
    python aggregate_submissions.py /path/to/folder/of/zips -o my_report
"""

import argparse
import csv
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

MIN_SUPPORTED_SCHEMA_VERSION = 3
MAX_SUPPORTED_SCHEMA_VERSION = 3  # bump alongside SUMMARY_SCHEMA_VERSION in export.py

SUMMARY_JSON_ARCNAME = "summary/summary.json"


def extract_summary(zip_path):
    """Return (summary_dict, error_message). error_message is None on success."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if SUMMARY_JSON_ARCNAME not in zf.namelist():
                return None, "no summary/summary.json found (older export, or export without logs)"
            with zf.open(SUMMARY_JSON_ARCNAME) as f:
                data = json.load(f)
            return data, None
    except zipfile.BadZipFile:
        return None, "not a valid zip file"
    except json.JSONDecodeError as e:
        return None, f"summary.json is not valid JSON: {e}"
    except Exception as e:
        return None, f"unexpected error reading zip: {e}"


def check_schema_version(summary):
    """Return None if OK, or a warning string if the version is out of the supported range."""
    version = summary.get("schema_version")
    if version is None:
        return "summary has no schema_version field (pre-versioning export); treating cautiously"
    if not (MIN_SUPPORTED_SCHEMA_VERSION <= version <= MAX_SUPPORTED_SCHEMA_VERSION):
        return (
            f"schema_version {version} is outside the range this aggregator "
            f"understands ({MIN_SUPPORTED_SCHEMA_VERSION}-{MAX_SUPPORTED_SCHEMA_VERSION}); "
            "values below may be missing or misinterpreted"
        )
    return None


def flatten_summary(zip_name, summary):
    """Flatten one summary dict into a single flat {column_name: value} row for CSV output."""
    row = {
        "zip_file": zip_name,
        "course_title": summary.get("course_title"),
        "schema_version": summary.get("schema_version"),
        "generated_at": summary.get("generated_at"),
    }

    counts = summary.get("counts", {})
    row["count_checkin"] = counts.get("checkin")
    row["count_inputlog"] = counts.get("inputlog")
    row["count_checkout"] = counts.get("checkout")
    row["count_total"] = counts.get("total")

    pairs = summary.get("session_pairs", {})
    row["complete_pairs"] = pairs.get("complete_pairs")
    row["orphaned_checkins"] = len(pairs.get("orphaned_checkins", []) or [])
    row["orphaned_checkouts"] = len(pairs.get("orphaned_checkouts", []) or [])

    inputs = summary.get("inputs", {})
    row["avg_inputs_per_inputlog"] = inputs.get("avg_inputs_per_inputlog")
    row["avg_inputs_per_session"] = inputs.get("avg_inputs_per_session")
    row["longest_input_length"] = (inputs.get("longest_input") or {}).get("length")

    for field_name, stats in (summary.get("scale_averages") or {}).items():
        row[f"scale_avg__{field_name}"] = stats.get("average")
        row[f"scale_answered__{field_name}"] = stats.get("count_answered")

    short = summary.get("short_responses", {})
    row["short_responses_total"] = short.get("total_short")
    for field_name, n in (short.get("by_field") or {}).items():
        row[f"short__{field_name}"] = n

    longest = summary.get("longest_entries", {})
    for field_name, entry in (longest.get("by_field") or {}).items():
        row[f"longest_len__{field_name}"] = (entry or {}).get("length")
    lr = longest.get("longest_reflection")
    row["longest_reflection_length"] = (lr or {}).get("length") if lr else None

    return row


def main():
    parser = argparse.ArgumentParser(
        description="Combine per-submission summary.json files (embedded in exported "
                     "submission zips) into one spreadsheet-friendly CSV, for scanning "
                     "trends across a whole class."
    )
    parser.add_argument("folder", type=Path, help="Folder containing student submission .zip files")
    parser.add_argument("-o", "--output", type=Path, default=Path("aggregate_report"),
                         help="Output file path prefix (default: ./aggregate_report)")
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"[ERROR] Not a folder: {args.folder}")
        sys.exit(1)

    zip_files = sorted(args.folder.glob("*.zip"))
    if not zip_files:
        print(f"[ERROR] No .zip files found in {args.folder}")
        sys.exit(1)

    rows = []
    skipped = []
    version_warnings = []

    for zip_path in zip_files:
        summary, err = extract_summary(zip_path)
        if err is not None:
            print(f"[SKIP] {zip_path.name}: {err}")
            skipped.append({"zip_file": zip_path.name, "reason": err})
            continue

        warning = check_schema_version(summary)
        if warning:
            print(f"[WARN] {zip_path.name}: {warning}")
            version_warnings.append({"zip_file": zip_path.name, "warning": warning})

        rows.append(flatten_summary(zip_path.name, summary))

    if not rows:
        print("[ERROR] No usable summaries found in any zip -- nothing to aggregate.")
        sys.exit(1)

    # Union of all column names across all rows, with a stable preferred ordering
    # for the well-known columns and any dynamic (config-driven) columns appended
    # afterward, sorted, so output is deterministic across runs.
    fixed_columns = [
        "zip_file", "course_title", "schema_version", "generated_at",
        "count_checkin", "count_inputlog", "count_checkout", "count_total",
        "complete_pairs", "orphaned_checkins", "orphaned_checkouts",
        "avg_inputs_per_inputlog", "avg_inputs_per_session", "longest_input_length",
        "short_responses_total", "longest_reflection_length",
    ]
    dynamic_columns = sorted({
        key for row in rows for key in row.keys() if key not in fixed_columns
    })
    all_columns = fixed_columns + dynamic_columns

    csv_path = args.output.with_suffix(".csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns, restval="")
        writer.writeheader()
        writer.writerows(rows)

    json_path = args.output.parent / f"{args.output.name}_full.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "zip_folder": str(args.folder),
            "submissions_processed": len(rows),
            "submissions_skipped": skipped,
            "schema_version_warnings": version_warnings,
            "rows": rows,
        }, f, indent=2)

    print(f"\n[OK] Aggregated {len(rows)} submission(s) into:")
    print(f"  {csv_path}")
    print(f"  {json_path}")
    if skipped:
        print(f"\n[NOTE] Skipped {len(skipped)} zip(s) without a usable summary (see above).")
    if version_warnings:
        print(f"[NOTE] {len(version_warnings)} zip(s) had schema-version warnings (see above).")


if __name__ == "__main__":
    main()
