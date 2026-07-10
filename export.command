#!/bin/bash
cd "$(dirname "$0")"

if [ ! -x "app/venv/bin/python" ]; then
    echo ""
    echo "The app hasn't been started yet, so there's nothing to export."
    echo "Please run start.command first, use the app for a session,"
    echo "then try export.command again."
    echo ""
    read -p "Press Enter to close this window..."
    exit 1
fi

app/venv/bin/python app/export.py

echo ""
read -p "Press Enter to close this window..."
