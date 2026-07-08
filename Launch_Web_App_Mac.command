#!/bin/bash

set -e

cd "$(dirname "$0")"

echo
echo "Greek Medical Report Anonymizer"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found."
  echo "Please install Python 3.10 or newer, then run this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import streamlit" >/dev/null 2>&1; then
  echo "Installing required packages..."
  python -m pip install --upgrade pip
  python -m pip install -e ".[ml,ui]"
fi

echo "Launching web app..."
echo "If the browser does not open automatically, go to http://localhost:8501"
echo

python -m streamlit run src/greek_med_anonymizer/web_app.py
