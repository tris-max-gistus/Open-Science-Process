#!/usr/bin/env python3
"""
Flask backend for LLM Usage Logger.
Reads config.yaml, serves forms, handles submissions.
"""

import os
import json
import time
import threading
import yaml
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, make_response

# Werkzeug's dev server enables SO_REUSEADDR by default, which on Windows
# allows a second instance to silently bind the same port instead of
# failing. That leaves stray old processes serving stale code alongside
# a new one, with requests landing on whichever accepts the connection.
# Disabling it makes a real port conflict raise a clear, loud error instead.
from werkzeug.serving import BaseWSGIServer
BaseWSGIServer.allow_reuse_address = False

# Anchor all paths to this file's location, not the process cwd, so the
# app behaves identically whether launched via start.py, a launcher
# script, or `python app.py` from an arbitrary directory.
APP_DIR = Path(__file__).resolve().parent      # UI/app  (config.yaml, next_hint.json live here)
PROJECT_ROOT = APP_DIR.parent                    # UI      (logs/, artifacts/ live here)

# Structurally load-bearing (used in artifact filenames/headers and validated
# server-side), so kept hardcoded rather than config-driven -- config-driving
# only the label while hardcoding the validated values would let a config
# edit silently desync from what the server actually accepts.
ARTIFACT_TAGS = ("helpful", "problematic", "personal_value")

app = Flask(__name__)

# Create logs and artifacts directories on startup
(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
(PROJECT_ROOT / "artifacts").mkdir(exist_ok=True)
(PROJECT_ROOT / "artifacts" / "process-log").mkdir(parents=True, exist_ok=True)

NEXT_HINT_FILE = APP_DIR / "next_hint.json"
SHUTDOWN_GRACE_SECONDS = 1.5

# Load config
def load_config():
    """Load form config from config.yaml."""
    if not (APP_DIR / "config.yaml").exists():
        print("Error: config.yaml not found.")
        exit(1)
    with open(APP_DIR / "config.yaml") as f:
        return yaml.safe_load(f)

CONFIG = load_config()
TITLE = CONFIG.get("title") or "LLM Usage Logger"

# Session state (in-memory, single student at a time)
# Structure: {
#   "session_id": "timestamp",
#   "inputlog_counter": 1,
#   "active_inputlog": {
#       "intent": "...", "own_understanding": "...",
#       "inputs": [{"index": 1, "text": "...", "timestamp": "..."}, ...],
#       "timestamp": "..."
#   }
# }
SESSION_STATE = {
    "session_id": None,
    "inputlog_counter": 0,
    "active_inputlog": None,
    "shutdown_token": 0,
    "current_checkin_goal": None,
    "current_checkin_timestamp": None
}

@app.before_request
def bump_shutdown_token():
    # Any incoming request (including a page reload) cancels a pending
    # auto-shutdown scheduled by a previous /api/shutdown beacon.
    SESSION_STATE["shutdown_token"] += 1

def get_session_id():
    """Get or create current session ID (timestamp-based)."""
    if SESSION_STATE["session_id"] is None:
        SESSION_STATE["session_id"] = datetime.now().strftime("%Y%m%d_%H%M%S")
        SESSION_STATE["inputlog_counter"] = 0
    return SESSION_STATE["session_id"]

def save_json(event_type, data):
    """Save event to JSON file in logs folder."""
    session_id = get_session_id()
    data["course_title"] = TITLE

    if event_type == "checkin":
        filename = f"session_{session_id}_checkin.json"
    elif event_type == "checkout":
        filename = f"session_{session_id}_checkout.json"
    elif event_type == "inputlog":
        SESSION_STATE["inputlog_counter"] += 1
        counter = SESSION_STATE["inputlog_counter"]
        filename = f"session_{session_id}_inputlog_{counter}.json"
    else:
        filename = f"session_{session_id}_{event_type}.json"

    filepath = PROJECT_ROOT / "logs" / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filename

# ============================================================================
# FRONTEND HTML/CSS/JS
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <script>
        // Applied before the stylesheet paints, so there's no flash of the
        // wrong theme on load.
        (function () {
            var saved = localStorage.getItem('theme');
            if (saved === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            }
        })();
    </script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --bg: #f3f4f6;
            --surface: #ffffff;
            --surface-alt: #f9fafb;
            --border: #e5e7eb;
            --border-strong: #d1d5db;
            --text: #111827;
            --text-muted: #6b7280;
            --text-faint: #9ca3af;
            --text-body: #374151;
            --text-body-alt: #4b5563;
            --accent: #0f766e;
            --accent-hover: #0d5f59;
            --dark-btn: #1f2937;
            --dark-btn-hover: #111827;
            --overlay: rgba(17, 24, 39, 0.45);
            --card-shadow: rgba(0, 0, 0, 0.06);
            --modal-shadow: rgba(0, 0, 0, 0.2);
            --error-text: #991b1b;
            --error-bg: #fef2f2;
            --error-border: #fecaca;
            --success-text: #166534;
            --success-bg: #f0fdf4;
            --success-border: #bbf7d0;
        }

        [data-theme="dark"] {
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-alt: #172033;
            --border: #334155;
            --border-strong: #475569;
            --text: #e5e7eb;
            --text-muted: #9ca3af;
            --text-faint: #6b7280;
            --text-body: #cbd5e1;
            --text-body-alt: #94a3b8;
            --accent: #14b8a6;
            --accent-hover: #2dd4bf;
            --dark-btn: #334155;
            --dark-btn-hover: #475569;
            --overlay: rgba(0, 0, 0, 0.6);
            --card-shadow: rgba(0, 0, 0, 0.4);
            --modal-shadow: rgba(0, 0, 0, 0.5);
            --error-text: #fca5a5;
            --error-bg: #450a0a;
            --error-border: #7f1d1d;
            --success-text: #86efac;
            --success-bg: #052e16;
            --success-border: #14532d;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: var(--text);
            transition: background 0.15s, color 0.15s;
        }

        .container {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 1px 3px var(--card-shadow);
            padding: 36px;
            max-width: 460px;
            width: 100%;
            position: relative;
        }

        .theme-toggle {
            position: absolute;
            top: 14px;
            right: 14px;
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-muted);
            border-radius: 999px;
            padding: 5px 10px;
            font-size: 12px;
            cursor: pointer;
        }

        .theme-toggle:hover {
            background: var(--surface-alt);
        }

        h1 {
            text-align: center;
            color: var(--text);
            margin-bottom: 6px;
            font-size: 21px;
            font-weight: 600;
        }

        .subtitle {
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            margin-bottom: 24px;
        }

        .continuity-box {
            background: var(--surface-alt);
            border: 1px solid var(--border);
            border-left: 3px solid var(--dark-btn);
            border-radius: 6px;
            padding: 12px 14px;
            margin-bottom: 24px;
        }

        .continuity-row {
            display: flex;
            gap: 8px;
            font-size: 13px;
            line-height: 1.5;
        }

        .continuity-row + .continuity-row {
            margin-top: 6px;
        }

        .continuity-label {
            flex-shrink: 0;
            color: var(--text-muted);
            font-weight: 600;
            min-width: 58px;
        }

        .continuity-text {
            color: var(--text-body);
            word-break: break-word;
        }

        .continuity-text.empty {
            color: var(--text-faint);
            font-style: italic;
        }

        .footnote {
            text-align: center;
            color: var(--text-faint);
            font-size: 11px;
            margin-top: 20px;
        }

        .button-grid {
            display: grid;
            gap: 10px;
        }

        button {
            padding: 14px;
            font-size: 15px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.15s;
            font-family: inherit;
        }

        .btn-checkin, .btn-inputlog, .btn-checkout {
            background: var(--dark-btn);
            color: white;
            text-align: left;
        }

        .btn-checkin:hover, .btn-inputlog:hover, .btn-checkout:hover {
            background: var(--dark-btn-hover);
        }

        .btn-inputlog.active-log {
            background: var(--accent);
        }

        .btn-inputlog.active-log:hover {
            background: var(--accent-hover);
        }

        .btn-count {
            float: right;
            font-weight: 400;
            opacity: 0.85;
            font-size: 13px;
        }

        /* Modal overlay */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--overlay);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }

        .modal-overlay.active {
            display: flex;
        }

        .modal {
            background: var(--surface);
            border-radius: 8px;
            padding: 28px;
            max-width: 560px;
            width: 90%;
            max-height: 88vh;
            overflow-y: auto;
            box-shadow: 0 10px 30px var(--modal-shadow);
        }

        .modal.modal-large {
            max-width: 720px;
            border-top: 3px solid var(--accent);
        }

        .modal h2 {
            color: var(--text);
            margin-bottom: 6px;
            font-size: 18px;
            font-weight: 600;
        }

        .modal-subtext {
            color: var(--text-muted);
            font-size: 13px;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 18px;
        }

        label {
            display: block;
            color: var(--text-body);
            font-weight: 500;
            margin-bottom: 6px;
            font-size: 13px;
        }

        textarea, input[type="text"], input[type="number"] {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border-strong);
            border-radius: 5px;
            font-family: inherit;
            font-size: 14px;
            color: var(--text);
            background: var(--surface);
        }

        textarea:focus, input[type="text"]:focus {
            outline: none;
            border-color: var(--text-muted);
        }

        textarea {
            resize: vertical;
            min-height: 76px;
            font-family: "Consolas", "Menlo", "Courier New", monospace;
            font-size: 13px;
        }

        textarea.log-entry-input {
            min-height: 120px;
            border: 1px solid var(--accent);
        }

        textarea.log-entry-input.entry-input {
            font-family: "Consolas", "Menlo", "Courier New", monospace;
            font-size: 13px;
        }

        textarea.log-entry-input.entry-note {
            font-family: inherit;
            font-size: 14px;
        }

        textarea::placeholder,
        input[type="text"]::placeholder {
            color: var(--text-faint);
        }

        /* Radio buttons for scale */
        .scale-group {
            display: flex;
            gap: 14px;
            margin-top: 6px;
        }

        .scale-option {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        input[type="radio"] {
            cursor: pointer;
            accent-color: var(--dark-btn);
        }

        .scale-option label {
            margin: 0;
            font-weight: 400;
            font-size: 13px;
        }

        /* Form buttons */
        .form-buttons {
            display: flex;
            gap: 8px;
            margin-top: 22px;
        }

        .btn-submit, .btn-cancel, .btn-secondary {
            flex: 1;
            padding: 11px;
            border: none;
            border-radius: 5px;
            font-weight: 500;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.15s;
            font-family: inherit;
        }

        .btn-submit {
            background: var(--dark-btn);
            color: white;
        }

        .btn-submit:hover {
            background: var(--dark-btn-hover);
        }

        .btn-secondary {
            background: var(--accent);
            color: white;
        }

        .btn-secondary:hover {
            background: var(--accent-hover);
        }

        .btn-cancel {
            background: var(--bg);
            color: var(--text-body);
            border: 1px solid var(--border-strong);
        }

        .btn-cancel:hover {
            background: var(--border);
        }

        .error {
            color: var(--error-text);
            background: var(--error-bg);
            border: 1px solid var(--error-border);
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 13px;
        }

        .success {
            color: var(--success-text);
            background: var(--success-bg);
            border: 1px solid var(--success-border);
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 13px;
        }

        .hint {
            color: var(--text-muted);
            font-size: 12px;
            margin-top: 4px;
        }

        /* Active input log panel */
        .log-summary {
            background: var(--surface-alt);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 14px;
            margin-bottom: 18px;
            font-size: 13px;
            color: var(--text-body-alt);
        }

        .log-summary strong {
            color: var(--text);
        }

        .input-count-badge {
            display: inline-block;
            background: var(--accent);
            color: white;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 6px;
        }

        .input-list {
            max-height: 180px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 18px;
        }

        .input-list-item {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }

        .input-list-item:last-child {
            border-bottom: none;
        }

        .input-list-item .input-index {
            color: var(--accent);
            font-weight: 600;
            font-size: 12px;
            margin-right: 6px;
        }

        .input-list-item .input-text {
            color: var(--text-body);
            white-space: pre-wrap;
            font-family: "Consolas", "Menlo", "Courier New", monospace;
            font-size: 12px;
        }

        .input-index.note-marker {
            color: var(--text-muted);
        }

        .note-text {
            color: var(--text-muted);
            font-size: 12px;
            font-style: italic;
            white-space: pre-wrap;
        }

        .input-list-empty {
            padding: 16px;
            text-align: center;
            color: var(--text-faint);
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <button class="theme-toggle" id="themeToggle" onclick="toggleTheme()">Dark mode</button>
        <h1>{{ title }}</h1>
        <div class="subtitle">Project Process Log</div>
        <div class="continuity-box">
            <div class="continuity-row">
                <span class="continuity-label">Last time</span>
                <span class="continuity-text" id="lastTimeText">&mdash;</span>
            </div>
            <div class="continuity-row">
                <span class="continuity-label">Today</span>
                <span class="continuity-text" id="todayText">&mdash;</span>
            </div>
        </div>
        <div class="button-grid">
            <button class="btn-checkin" onclick="openModal('checkin')">
                Session Check-In
            </button>
            <button class="btn-inputlog" id="inputlogBtn" onclick="openModal('inputlog')">
                Process Log
            </button>
            <button class="btn-checkout" onclick="openModal('checkout')">
                Session Check-Out
            </button>
        </div>
        <div class="footnote">Closing this tab stops the local server.</div>
    </div>

    <!-- Modal for forms -->
    <div class="modal-overlay" id="modalOverlay">
        <div class="modal" id="modal">
            <!-- Content injected by JS -->
        </div>
    </div>

    <script>
        const CONFIG = {};
        let sessionState = {};

        function updateThemeToggleLabel() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            document.getElementById('themeToggle').textContent = isDark ? 'Light mode' : 'Dark mode';
        }

        function toggleTheme() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            if (isDark) {
                document.documentElement.removeAttribute('data-theme');
                localStorage.setItem('theme', 'light');
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            }
            updateThemeToggleLabel();
        }

        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                Object.assign(CONFIG, await response.json());
            } catch (error) {
                console.error('Failed to load config:', error);
            }
        }

        async function loadSessionState() {
            try {
                const response = await fetch('/api/session-state');
                Object.assign(sessionState, await response.json());
                updateButtonLabels();
                updateContinuityToday();
            } catch (error) {
                console.error('Failed to load session state:', error);
            }
        }

        function updateButtonLabels() {
            const btn = document.getElementById('inputlogBtn');
            const active = sessionState.active_inputlog;
            if (active && active.inputs) {
                const n = active.inputs.length;
                btn.classList.add('active-log');
                btn.innerHTML = `Process Log <span class="btn-count">${n} logged &mdash; continue</span>`;
            } else {
                btn.classList.remove('active-log');
                btn.textContent = 'Process Log';
            }
        }

        function updateContinuityToday() {
            const el = document.getElementById('todayText');
            const goal = sessionState.current_checkin_goal;
            if (goal) {
                el.textContent = goal;
                el.classList.remove('empty');
            } else {
                el.textContent = 'Not checked in yet this session';
                el.classList.add('empty');
            }
        }

        async function loadLastTime() {
            const el = document.getElementById('lastTimeText');
            try {
                const response = await fetch('/api/next-hint');
                const hint = await response.json();
                if (hint.text) {
                    el.textContent = hint.text;
                    el.classList.remove('empty');
                } else {
                    el.textContent = "No note yet — fills in after your first check-out";
                    el.classList.add('empty');
                }
            } catch (error) {
                console.error('Failed to load last-time note:', error);
            }
        }

        async function openModal(eventType) {
            await configReady;
            await loadSessionState();

            if (eventType === 'inputlog') {
                if (sessionState.active_inputlog) {
                    renderActiveInputLog();
                } else {
                    renderInputLogStart();
                }
                document.getElementById('modalOverlay').classList.add('active');
                return;
            }

            const config = CONFIG[eventType];
            if (!config) {
                console.error('Config not found for', eventType);
                return;
            }

            const modal = document.getElementById('modal');
            modal.classList.remove('modal-large');
            let html = `<h2>${getTitle(eventType)}</h2>`;

            let substitutions = {};
            if (eventType === 'checkout') {
                const checkinTs = sessionState.current_checkin_timestamp;
                if (checkinTs) {
                    const hours = (Date.now() - new Date(checkinTs).getTime()) / 3600000;
                    substitutions.hours = `${hours.toFixed(1)} hours`;
                } else {
                    substitutions.hours = 'an unknown amount of time';
                }
            }

            config.forEach(fieldConfig => {
                html += createFormField(fieldConfig, substitutions);
            });

            html += `
                <div class="form-buttons">
                    <button class="btn-submit" onclick="submitForm('${eventType}')">Document</button>
                    <button class="btn-cancel" onclick="closeModal()">Cancel</button>
                </div>
            `;

            modal.innerHTML = html;
            document.getElementById('modalOverlay').classList.add('active');

            if (eventType === 'checkin') {
                prefillGoalFromHint();
            }
        }

        async function prefillGoalFromHint() {
            try {
                const response = await fetch('/api/next-hint');
                const hint = await response.json();
                const goalField = document.getElementById('goal');
                console.log('[prefill] hint from server:', hint, 'goalField found:', !!goalField, 'goalField current value:', goalField ? goalField.value : null);
                if (hint.text && goalField && !goalField.value) {
                    goalField.value = hint.text;
                    console.log('[prefill] goal field set to:', hint.text);
                } else {
                    console.log('[prefill] did not set goal field (no hint text, no field, or field already had a value)');
                }
            } catch (error) {
                console.error('[prefill] Failed to load next-session hint:', error);
            }
        }

        function renderInputLogStart() {
            const modal = document.getElementById('modal');
            modal.classList.remove('modal-large');

            const intentConfig = CONFIG.inputlog.find(f => f.field === 'intent');
            const understandingConfig = CONFIG.inputlog.find(f => f.field === 'own_understanding');

            let html = `
                <h2>Start Process Log</h2>
                <div class="modal-subtext">Answer these before you open the LLM. This starts one log for the whole work block &mdash; you'll add individual inputs to it as you go.</div>
            `;
            html += createFormField(intentConfig);
            html += createFormField(understandingConfig);
            html += `
                <div class="form-buttons">
                    <button class="btn-secondary" onclick="startInputLog()">Begin Log</button>
                    <button class="btn-cancel" onclick="closeModal()">Cancel</button>
                </div>
            `;

            modal.innerHTML = html;
        }

        async function startInputLog() {
            const intent = document.getElementById('intent')?.value || '';
            const own_understanding = document.getElementById('own_understanding')?.value || '';

            try {
                const response = await fetch('/api/inputlog/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ intent, own_understanding })
                });

                if (response.ok) {
                    await loadSessionState();
                    renderActiveInputLog();
                } else {
                    showError('Failed to start log');
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        }

        function renderActiveInputLog() {
            const modal = document.getElementById('modal');
            modal.classList.add('modal-large');

            const active = sessionState.active_inputlog;
            const inputConfig = CONFIG.inputlog.find(f => f.field === 'inputs');
            const notesConfig = CONFIG.inputlog.find(f => f.field === 'input_notes');
            const entries = (active && active.inputs) || [];

            let listHtml = '';
            if (entries.length === 0) {
                listHtml = '<div class="input-list-empty">Nothing logged yet</div>';
            } else {
                listHtml = entries.map(e => e.type === 'note' ? `
                    <div class="input-list-item">
                        <span class="input-index note-marker">-</span>
                        <span class="note-text">${escapeHtml(e.text)}</span>
                    </div>
                ` : `
                    <div class="input-list-item">
                        <span class="input-index">#${e.index}</span>
                        <span class="input-text">${escapeHtml(e.text)}</span>
                    </div>
                `).join('');
            }

            let html = `
                <h2>Process Log <span class="input-count-badge">${entries.length} logged</span></h2>
                <div class="log-summary">
                    <strong>Intent:</strong> ${escapeHtml(active.intent || '')}
                </div>
                <div class="input-list">${listHtml}</div>
                <div class="form-group">
                    <label for="new_input_text">${inputConfig.label}</label>
                    <textarea id="new_input_text" class="log-entry-input entry-input" placeholder="${inputConfig.placeholder || ''}"></textarea>
                </div>
                <div class="form-buttons">
                    <button class="btn-secondary" onclick="addInput()">Add Input</button>
                </div>
                <div class="form-group">
                    <label for="new_note_text">${notesConfig.label}</label>
                    <textarea id="new_note_text" class="log-entry-input entry-note" placeholder="${notesConfig.placeholder || ''}"></textarea>
                </div>
                <div class="form-buttons">
                    <button class="btn-secondary" onclick="addNote()">Add Note</button>
                </div>
                <div class="form-buttons">
                    <button class="btn-cancel" onclick="renderArtifactForm()">Save an LLM Output</button>
                    <button class="btn-submit" onclick="renderReflectionForm()">Finish &amp; Reflect</button>
                </div>
                <div class="form-buttons">
                    <button class="btn-cancel" onclick="closeModal()">Close (keep log open)</button>
                </div>
            `;

            modal.innerHTML = html;
        }

        async function addInput() {
            const text = document.getElementById('new_input_text')?.value || '';
            if (!text.trim()) return;

            try {
                const response = await fetch('/api/inputlog/add-input', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });

                if (response.ok) {
                    await loadSessionState();
                    renderActiveInputLog();
                } else {
                    showError('Failed to add input');
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        }

        async function addNote() {
            const text = document.getElementById('new_note_text')?.value || '';
            if (!text.trim()) return;

            try {
                const response = await fetch('/api/inputlog/add-note', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });

                if (response.ok) {
                    await loadSessionState();
                    renderActiveInputLog();
                } else {
                    showError('Failed to add note');
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        }

        function renderArtifactForm() {
            const modal = document.getElementById('modal');
            modal.classList.remove('modal-large');

            const contentConfig = CONFIG.artifact.find(f => f.field === 'artifact_content');
            const categoryConfig = CONFIG.artifact.find(f => f.field === 'artifact_category');
            const tags = [['helpful', 'Helpful'], ['problematic', 'Problematic'], ['personal_value', 'Personal value']];

            let html = `
                <h2>Save an LLM Output</h2>
                <div class="modal-subtext">This is the place to log helpful model Outputs and other products generated by the process.</div>
                <div class="form-group">
                    <label for="artifact_content">${contentConfig.label}</label>
                    <textarea id="artifact_content" class="log-entry-input entry-note" placeholder="${contentConfig.placeholder || ''}"></textarea>
                </div>
                <div class="form-group">
                    <label for="artifact_category">${categoryConfig.label}</label>
                    <input type="text" id="artifact_category" placeholder="${categoryConfig.placeholder || ''}">
                </div>
                <div class="form-group">
                    <label>How would you flag it?</label>
                    <div class="scale-group">
                        ${tags.map(([val, text]) => `
                            <div class="scale-option">
                                <input type="radio" id="artifact_tag_${val}" name="artifact_tag" value="${val}">
                                <label for="artifact_tag_${val}">${text}</label>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="form-buttons">
                    <button class="btn-submit" onclick="submitArtifact()">Document</button>
                    <button class="btn-cancel" onclick="renderActiveInputLog()">Cancel</button>
                </div>
            `;

            modal.innerHTML = html;
        }

        async function submitArtifact() {
            const content = document.getElementById('artifact_content')?.value || '';
            const category = document.getElementById('artifact_category')?.value || '';
            const tag = document.querySelector('input[name="artifact_tag"]:checked')?.value || '';

            if (!content.trim()) {
                showError('Paste something before documenting it.');
                return;
            }
            if (!tag) {
                showError('Pick how to flag it.');
                return;
            }

            try {
                const response = await fetch('/api/inputlog/artifact', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content, category, tag })
                });

                if (response.ok) {
                    showNotification('Artifact saved');
                    renderActiveInputLog();
                } else {
                    showError('Failed to save artifact');
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        }

        function renderReflectionForm() {
            const modal = document.getElementById('modal');
            modal.classList.remove('modal-large');

            const outcomeConfig = CONFIG.inputlog.find(f => f.field === 'reflection_outcome');
            const errorsConfig = CONFIG.inputlog.find(f => f.field === 'reflection_errors');
            const surprisesConfig = CONFIG.inputlog.find(f => f.field === 'reflection_surprises');
            const active = sessionState.active_inputlog;
            const n = (active && active.inputs) ? active.inputs.filter(p => p.type === 'input').length : 0;

            let html = `
                <h2>Finish This Process Log</h2>
                <div class="modal-subtext">${n} input${n === 1 ? '' : 's'} logged in this block. Reflect before closing it out.</div>
            `;
            html += createFormField(outcomeConfig);
            html += createFormField(errorsConfig);
            html += createFormField(surprisesConfig);
            html += `
                <div class="form-buttons">
                    <button class="btn-submit" onclick="submitReflection()">Save &amp; Close Log</button>
                    <button class="btn-cancel" onclick="renderActiveInputLog()">Back</button>
                </div>
            `;

            modal.innerHTML = html;
        }

        function createFormField(fieldConfig, substitutions = {}) {
            const { field, placeholder, type } = fieldConfig;
            let label = fieldConfig.label;
            for (const [key, val] of Object.entries(substitutions)) {
                label = label.split(`{${key}}`).join(val);
            }

            if (type === 'textarea') {
                return `
                    <div class="form-group">
                        <label for="${field}">${label}</label>
                        <textarea id="${field}" placeholder="${placeholder || ''}"></textarea>
                    </div>
                `;
            } else if (type === 'text') {
                return `
                    <div class="form-group">
                        <label for="${field}">${label}</label>
                        <input type="text" id="${field}" placeholder="${placeholder || ''}">
                    </div>
                `;
            } else if (type === 'scale_1_5') {
                return `
                    <div class="form-group">
                        <label>${label}</label>
                        <div class="scale-group">
                            ${[1, 2, 3, 4, 5].map(num => `
                                <div class="scale-option">
                                    <input type="radio" id="${field}_${num}" name="${field}" value="${num}">
                                    <label for="${field}_${num}">${num}</label>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            return '';
        }

        function getTitle(eventType) {
            const titles = {
                checkin: 'Session Check-In',
                inputlog: 'Process Log',
                checkout: 'Session Check-Out'
            };
            return titles[eventType] || 'Form';
        }

        async function submitForm(eventType) {
            const config = CONFIG[eventType];
            const data = {};

            config.forEach(fieldConfig => {
                data[fieldConfig.field] = getFieldValue(fieldConfig);
            });

            try {
                const response = await fetch(`/api/${eventType}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    closeModal();
                    showNotification(`${getTitle(eventType)} saved`);
                    await loadSessionState();
                } else {
                    showError('Failed to save form');
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        }

        async function submitReflection() {
            const reflection_outcome = document.getElementById('reflection_outcome')?.value || '';
            const reflection_errors = document.getElementById('reflection_errors')?.value || '';
            const reflection_surprises = document.getElementById('reflection_surprises')?.value || '';

            try {
                const response = await fetch('/api/inputlog-reflection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reflection_outcome, reflection_errors, reflection_surprises })
                });

                if (response.ok) {
                    await loadSessionState();
                    closeModal();
                    showNotification('Input log saved');
                } else {
                    showError('Failed to save reflection');
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        }

        function getFieldValue(fieldConfig) {
            const { field, type } = fieldConfig;
            const element = document.getElementById(field);

            if (type === 'scale_1_5') {
                return document.querySelector(`input[name="${field}"]:checked`)?.value || '';
            } else {
                return element?.value || '';
            }
        }

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        function closeModal() {
            document.getElementById('modalOverlay').classList.remove('active');
        }

        function showError(message) {
            const modal = document.getElementById('modal');
            const existing = modal.querySelector('.error');
            if (existing) existing.remove();

            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = message;
            modal.insertBefore(errorDiv, modal.firstChild);
        }

        function showNotification(message) {
            const div = document.createElement('div');
            div.className = 'success';
            div.textContent = message;
            div.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 2000; max-width: 400px;';
            document.body.appendChild(div);
            setTimeout(() => div.remove(), 3000);
        }

        document.getElementById('modalOverlay').addEventListener('click', (e) => {
            if (e.target === document.getElementById('modalOverlay')) {
                closeModal();
            }
        });

        // Ping the server on tab close so it can shut itself down.
        // A page reload also fires this, but the server cancels the
        // shutdown if it sees a new request (like this reload) within
        // its grace window, so refreshing is safe.
        window.addEventListener('beforeunload', () => {
            navigator.sendBeacon('/api/shutdown');
        });

        updateThemeToggleLabel();
        const configReady = loadConfig();
        loadSessionState();
        loadLastTime();
    </script>
</body>
</html>
"""

# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    resp = make_response(render_template_string(HTML_TEMPLATE, title=TITLE))
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/api/config")
def get_config():
    """Return form configuration."""
    return jsonify(CONFIG)

@app.route("/api/session-state")
def get_session_state():
    """Return current session state (active input log, etc)."""
    return jsonify({
        "session_id": SESSION_STATE["session_id"],
        "inputlog_counter": SESSION_STATE["inputlog_counter"],
        "active_inputlog": SESSION_STATE["active_inputlog"],
        "current_checkin_goal": SESSION_STATE["current_checkin_goal"],
        "current_checkin_timestamp": SESSION_STATE["current_checkin_timestamp"]
    })

@app.route("/api/next-hint")
def get_next_hint():
    """Return the next_start note from the last check-out, if any."""
    if NEXT_HINT_FILE.exists():
        with open(NEXT_HINT_FILE) as f:
            return jsonify(json.load(f))
    return jsonify({"text": None})

@app.route("/api/checkin", methods=["POST"])
def submit_checkin():
    """Save check-in form."""
    data = request.json
    data["timestamp"] = datetime.now().isoformat()
    get_session_id()  # Initialize session
    save_json("checkin", data)
    SESSION_STATE["current_checkin_goal"] = data.get("goal", "")
    SESSION_STATE["current_checkin_timestamp"] = data["timestamp"]
    return jsonify({"status": "ok"})

@app.route("/api/checkout", methods=["POST"])
def submit_checkout():
    """Save check-out form."""
    data = request.json
    data["timestamp"] = datetime.now().isoformat()

    checkin_ts = SESSION_STATE.get("current_checkin_timestamp")
    if checkin_ts:
        elapsed = (datetime.now() - datetime.fromisoformat(checkin_ts)).total_seconds() / 3600
        data["elapsed_hours"] = round(elapsed, 2)
    else:
        data["elapsed_hours"] = None

    save_json("checkout", data)

    # Persist next_start as a hint for the next session's check-in
    with open(NEXT_HINT_FILE, "w") as f:
        json.dump({
            "text": data.get("next_start", ""),
            "timestamp": data["timestamp"]
        }, f, indent=2)

    return jsonify({"status": "ok"})

@app.route("/api/inputlog/start", methods=["POST"])
def start_inputlog():
    """Begin a new active input log (intent + own_understanding)."""
    data = request.json
    get_session_id()
    SESSION_STATE["active_inputlog"] = {
        "intent": data.get("intent", ""),
        "own_understanding": data.get("own_understanding", ""),
        "inputs": [],
        "timestamp": datetime.now().isoformat()
    }
    return jsonify({"status": "ok", "active_inputlog": SESSION_STATE["active_inputlog"]})

@app.route("/api/inputlog/add-input", methods=["POST"])
def add_input():
    """Append one input entry to the active input log."""
    if not SESSION_STATE["active_inputlog"]:
        return jsonify({"status": "error", "message": "No active input log"}), 400

    data = request.json
    text = data.get("text", "")
    inputs = SESSION_STATE["active_inputlog"]["inputs"]
    next_index = len([p for p in inputs if p.get("type") == "input"]) + 1
    inputs.append({
        "type": "input",
        "index": next_index,
        "text": text,
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"status": "ok", "active_inputlog": SESSION_STATE["active_inputlog"]})

@app.route("/api/inputlog/add-note", methods=["POST"])
def add_note():
    """Append one note entry to the active input log (independent of inputs, not numbered)."""
    if not SESSION_STATE["active_inputlog"]:
        return jsonify({"status": "error", "message": "No active input log"}), 400

    data = request.json
    text = data.get("text", "")
    inputs = SESSION_STATE["active_inputlog"]["inputs"]
    inputs.append({
        "type": "note",
        "index": None,
        "text": text,
        "timestamp": datetime.now().isoformat()
    })
    return jsonify({"status": "ok", "active_inputlog": SESSION_STATE["active_inputlog"]})

@app.route("/api/inputlog/artifact", methods=["POST"])
def add_artifact():
    """Save a flagged LLM response as a JSON artifact. No inputlog-JSON-log involvement."""
    if not SESSION_STATE["active_inputlog"]:
        return jsonify({"status": "error", "message": "No active input log"}), 400

    data = request.json or {}
    content = (data.get("content") or "").strip()
    category = (data.get("category") or "").strip()
    tag = data.get("tag") or ""
    if tag not in ARTIFACT_TAGS:
        return jsonify({"status": "error", "message": "Invalid tag"}), 400
    if not content:
        return jsonify({"status": "error", "message": "Artifact content is empty"}), 400

    artifact_dir = PROJECT_ROOT / "artifacts" / "process-log"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"artifact_{stamp}_{tag}.json"
    filepath = artifact_dir / filename
    suffix = 2
    while filepath.exists():
        filename = f"artifact_{stamp}_{tag}_{suffix}.json"
        filepath = artifact_dir / filename
        suffix += 1

    artifact_data = {
        "category": category,
        "text": content,
        "tag": tag,
        "timestamp": now.isoformat(),
        "session_id": SESSION_STATE["session_id"],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(artifact_data, f, indent=2)

    return jsonify({"status": "ok", "filename": filename})

@app.route("/api/inputlog-reflection", methods=["POST"])
def submit_inputlog_reflection():
    """Save reflection to active input log and finalize it."""
    data = request.json

    if SESSION_STATE["active_inputlog"]:
        SESSION_STATE["active_inputlog"]["reflection_outcome"] = data.get("reflection_outcome", "")
        SESSION_STATE["active_inputlog"]["reflection_errors"] = data.get("reflection_errors", "")
        SESSION_STATE["active_inputlog"]["reflection_surprises"] = data.get("reflection_surprises", "")
        SESSION_STATE["active_inputlog"]["reflection_timestamp"] = datetime.now().isoformat()
        save_json("inputlog", SESSION_STATE["active_inputlog"])
        SESSION_STATE["active_inputlog"] = None

    return jsonify({"status": "ok"})

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """
    Stop the server shortly after the browser tab is closed.
    The token check gives a page reload (which fires another request within
    the grace window and bumps the token via bump_shutdown_token) a chance
    to cancel the exit, so refreshing the page doesn't kill the server.
    """
    token = SESSION_STATE["shutdown_token"]

    def stop():
        time.sleep(SHUTDOWN_GRACE_SECONDS)
        if SESSION_STATE["shutdown_token"] == token:
            os._exit(0)

    threading.Thread(target=stop, daemon=True).start()
    return ("", 204)

if __name__ == "__main__":
    print("Starting LLM Usage Logger on http://localhost:5000")
    print("Closing the browser tab will automatically stop this server.")
    try:
        app.run(debug=False, port=5000)
    except OSError as e:
        print(f"\n[ERROR] Could not start server: {e}")
        print("This usually means port 5000 is already in use by another")
        print("copy of this app still running from an earlier session.")
        print("Close any old terminal windows running this app (or find")
        print("and end the stray python.exe process) and try again.")
        raise
