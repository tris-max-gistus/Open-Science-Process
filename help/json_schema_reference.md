# How This Tool Stores Your Process as JSON

This is a reference for what's actually inside the files in `/logs`, `/artifacts`, and inside an exported submission zip's `/summary` folder — and why they're shaped the way they are. It's written for anyone curious about the back-end structure, not just how to use the app.

## The core idea

Every event in a work session — checking in, logging an input, checking out — becomes **one flat JSON file**, written the moment you submit the form. Nothing is inferred, summarized, or transformed at write time: the file is a direct, literal record of what you typed. JSON is just a text format for representing that record as nested `"key": value` pairs, so it's both easy for the app to read back and easy for a human to open and read directly.

This is "process abstraction" in its simplest form: instead of trying to capture your whole work session as one blob, the tool breaks it into a small number of well-defined **event types**, each with a fixed, predictable shape. A whole process becomes a folder of small, dated, typed records rather than one unstructured document.

## The event files (`/logs`)

### `session_<id>_checkin.json`
One per Session Check-In.

| field | type | meaning |
|---|---|---|
| `goal` | string | what you intend to accomplish this session |
| `planned_duration` | string | free-text time estimate |
| `checkin_notes` | string | anything else worth noting |
| `timestamp` | string (ISO 8601) | when submitted |
| `course_title` | string | stamped in automatically from `config.yaml` |

### `session_<id>_inputlog_<n>.json`
One per Process Log block (the `<n>` counts up if you start more than one log in a session).

| field | type | meaning |
|---|---|---|
| `intent` | string | what you're trying to do and expect to get |
| `own_understanding` | string | your own prediction, written *before* using the LLM |
| `inputs` | array of objects | the chronological log of the block — see below |
| `timestamp` | string (ISO 8601) | when the block started |
| `reflection_outcome` | string | what happened, post-hoc |
| `reflection_errors` | string | frustrations, limitations hit |
| `reflection_surprises` | string | what worked better than expected |
| `reflection_timestamp` | string (ISO 8601) | when the block was closed |

The `inputs` array is the most interesting structure in the app: each entry is `{"type": "input" | "note", "index": number or null, "text": string, "timestamp": string}`. Inputs and notes are interleaved in the exact order you added them — the array itself *is* the trace of your process, not a summary of one. Inputs are numbered (`index`); notes aren't (`index` is `null`), since notes are asides rather than steps.

### `session_<id>_checkout.json`
One per Session Check-Out.

| field | type | meaning |
|---|---|---|
| `duration_actual` | string | reflection on time-spent quality |
| `final_thoughts` | string | open reflection |
| `next_start` | string | carried forward to prefill your next check-in |
| `confidence` / `clarity` / `support` | string, `"1"`-`"5"` | self-report scales |
| `elapsed_hours` | number or `null` | **the one field you never type** — computed server-side from the time between check-in and check-out |
| `timestamp` | string (ISO 8601) | when submitted |
| `course_title` | string | stamped in automatically |

## Artifacts (`/artifacts/process-log`)

`artifact_<timestamp>_<tag>.json` — a flagged LLM output, saved separately from the main log because it's the *only* place in the whole tool where the model's output itself is stored (everywhere else records only what you typed).

| field | type | meaning |
|---|---|---|
| `category` | string | free-text topic/handle |
| `text` | string | the flagged output |
| `tag` | string | `"helpful"`, `"problematic"`, or `"personal_value"` |
| `timestamp` | string (ISO 8601) | |
| `session_id` | string | links it back to a session, since it has no other connection to a log file |

## `summary/summary.json` (export time only)

When you export, `app/export.py` reads every file above and computes one more JSON file — purely derived, no new data collected. It's one level of abstraction up: counts, averages, and longest entries, rather than raw events.

Key sections: `counts` (how many of each event type), `session_pairs` (check-in/check-out matching), `inputs` (`avg_inputs_per_inputlog`, `avg_inputs_per_session`, `inputlog_file_count`, `session_count_with_inputlogs`, `longest_input`), `scale_averages` (per checkout scale field), `short_responses` and `longest_entries` (per text field, config-driven), and `caveats` (known limitations of the analysis, written in plain language).

A `schema_version` field is included so a downstream tool (like `app/aggregate_submissions.py`, which combines many students' `summary.json` files into one class-wide CSV) can detect if it's reading a shape it doesn't understand, rather than silently misreading renamed or restructured fields.

## Why this design

- **Config-driven, not hardcoded.** `app/config.yaml` defines every question's wording; the JSON `field` names it uses are stable identifiers, decoupled from whatever text an instructor edits them to. Changing a question's wording never changes the data's shape.
- **Flat and typed, not deeply nested.** Each file answers "what happened at this one moment," so a human (or a script) can read it in isolation without needing the rest of the session for context.
- **Append, don't rewrite.** The `inputs` array only ever grows during a session — nothing is edited or deleted once written — so the file is an honest, order-preserving trace, not a cleaned-up final draft.
