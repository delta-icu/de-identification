#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")"

echo
echo "Greek Medical Report Anonymizer"
echo

MIN_MAJOR=3
MIN_MINOR=10
CONDA_PY_VERSION="3.11"
CONDA_ENV_NAME="greek-med-arm"
APP_PORT="8501"

PY_CMD=""
ENV_LABEL=""

fail() {
  echo
  echo "$@"
  echo
  read -r -p "Press Enter to close..."
  exit 1
}

# True if the given python binary exists and is new enough.
python_ok() {
  local candidate="$1"
  if [ ! -x "$candidate" ] && ! command -v "$candidate" >/dev/null 2>&1; then
    return 1
  fi
  "$candidate" -c \
    "import sys; raise SystemExit(0 if sys.version_info >= (${MIN_MAJOR}, ${MIN_MINOR}) else 1)" \
    >/dev/null 2>&1
}

python_version_of() {
  "$1" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo "unknown"
}


# ---------------------------------------------------------------------------
# Stage 1: an already-active conda environment, if it is new enough
# ---------------------------------------------------------------------------

if [ -z "$PY_CMD" ] && [ -n "${CONDA_PREFIX:-}" ]; then
  if python_ok "${CONDA_PREFIX}/bin/python"; then
    PY_CMD="${CONDA_PREFIX}/bin/python"
    ENV_LABEL="active conda environment (Python $(python_version_of "$PY_CMD"))"
  else
    echo "Active conda environment has Python $(python_version_of "${CONDA_PREFIX}/bin/python"); too old, skipping it."
  fi
fi

# ---------------------------------------------------------------------------
# Stage 2: an existing .venv, if it is new enough (otherwise rebuild it)
# ---------------------------------------------------------------------------

if [ -z "$PY_CMD" ] && [ -x ".venv/bin/python" ]; then
  if python_ok ".venv/bin/python"; then
    PY_CMD=".venv/bin/python"
    ENV_LABEL="local .venv (Python $(python_version_of "$PY_CMD"))"
  else
    echo "Existing .venv has Python $(python_version_of ".venv/bin/python"); too old, removing it."
    rm -rf .venv
  fi
fi

# ---------------------------------------------------------------------------
# Stage 3: any suitable python3.x on the system -> build a fresh .venv
# ---------------------------------------------------------------------------

if [ -z "$PY_CMD" ]; then
  BASE_PY=""
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if python_ok "$candidate"; then
      BASE_PY="$candidate"
      break
    fi
  done

  if [ -n "$BASE_PY" ]; then
    echo "Found $BASE_PY (Python $(python_version_of "$BASE_PY"))."
    echo "Creating local virtual environment..."
    rm -rf .venv
    "$BASE_PY" -m venv .venv || fail "Could not create the virtual environment."
    PY_CMD=".venv/bin/python"
    ENV_LABEL="local .venv (Python $(python_version_of "$PY_CMD"))"
  fi
fi

# ---------------------------------------------------------------------------
# Stage 4: fall back to a dedicated conda environment with a pinned Python
# ---------------------------------------------------------------------------

if [ -z "$PY_CMD" ]; then
  CONDA_BIN=""
  if [ -n "${CONDA_EXE:-}" ] && [ -x "${CONDA_EXE}" ]; then
    CONDA_BIN="${CONDA_EXE}"
  elif command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
  else
    for guess in \
      "$HOME/miniconda3/bin/conda" \
      "$HOME/anaconda3/bin/conda" \
      "$HOME/miniforge3/bin/conda" \
      "$HOME/mambaforge/bin/conda" \
      "$HOME/opt/miniconda3/bin/conda" \
      "$HOME/opt/anaconda3/bin/conda" \
      "/opt/homebrew/Caskroom/miniconda/base/bin/conda" \
      "/opt/miniconda3/bin/conda" \
      "/opt/anaconda3/bin/conda"
    do
      if [ -x "$guess" ]; then
        CONDA_BIN="$guess"
        break
      fi
    done
  fi

  if [ -n "$CONDA_BIN" ]; then
    echo "No suitable Python found on the system. Using conda instead."

    conda_env_prefix() {
      "$CONDA_BIN" env list 2>/dev/null | awk -v name="$CONDA_ENV_NAME" '
        /^#/ { next }
        $1 == name { sub(/\/$/, "", $NF); print $NF; exit }
      '
    }

    ENV_PREFIX="$(conda_env_prefix || true)"

    if [ -n "$ENV_PREFIX" ] && python_ok "${ENV_PREFIX}/bin/python"; then
      : # existing env is fine
    elif [ -n "$ENV_PREFIX" ]; then
      echo "Conda environment '${CONDA_ENV_NAME}' exists but its Python is too old; updating it to ${CONDA_PY_VERSION}..."
      "$CONDA_BIN" install -y -n "$CONDA_ENV_NAME" "python=${CONDA_PY_VERSION}" \
        || fail "Could not update the conda environment '${CONDA_ENV_NAME}'."
    else
      echo "Creating conda environment '${CONDA_ENV_NAME}' with Python ${CONDA_PY_VERSION}..."
      echo "This can take several minutes the first time."
      "$CONDA_BIN" create -y -n "$CONDA_ENV_NAME" "python=${CONDA_PY_VERSION}" \
        || fail "Could not create the conda environment '${CONDA_ENV_NAME}'."
      ENV_PREFIX="$(conda_env_prefix || true)"
    fi

    [ -n "$ENV_PREFIX" ] || fail "Could not locate the conda environment '${CONDA_ENV_NAME}' after creating it."

    # Call the environment's interpreter by full path - no 'conda activate' needed.
    if python_ok "${ENV_PREFIX}/bin/python"; then
      PY_CMD="${ENV_PREFIX}/bin/python"
      ENV_LABEL="conda environment '${CONDA_ENV_NAME}' (Python $(python_version_of "$PY_CMD"))"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Nothing worked: explain exactly what to do
# ---------------------------------------------------------------------------

if [ -z "$PY_CMD" ]; then
  FOUND_NOTE="none found"
  if command -v python3 >/dev/null 2>&1; then
    FOUND_NOTE="the python3 on this Mac is $(python_version_of python3)"
  fi

  fail "$(cat <<MSG
This app needs Python ${MIN_MAJOR}.${MIN_MINOR} or newer, but ${FOUND_NOTE}.

Pick one of these, then double-click this file again:

  1. Install Python from https://www.python.org/downloads/
     (any version ${MIN_MAJOR}.${MIN_MINOR} or newer)

  2. Or, if you use conda, run this once in Terminal:
     conda create -n ${CONDA_ENV_NAME} python=${CONDA_PY_VERSION} -y
MSG
)"
fi

echo "Using ${ENV_LABEL}."

# ---------------------------------------------------------------------------
# Dependencies and launch
# ---------------------------------------------------------------------------

# streamlit is the last thing installed, so its absence means the install has
# not run. torch is checked too: it can be missing while streamlit imports fine.
if ! "$PY_CMD" -c "import streamlit, torch, transformers" >/dev/null 2>&1; then
  echo "Installing required packages. The first time this can take several minutes..."
  "$PY_CMD" -m pip install --upgrade pip || fail "Could not upgrade pip."
  "$PY_CMD" -m pip install -e ".[ml,ui]" || fail "Could not install the required packages."

  if ! "$PY_CMD" -c "import streamlit, torch, transformers" >/dev/null 2>&1; then
    echo
    echo "Packages are installed, but one of them will not load. Details:"
    "$PY_CMD" -c "import streamlit, torch, transformers" || true
    fail "The app cannot start until the error above is resolved."
  fi
fi

# Streamlit shows a one-time "enter your email" prompt on a fresh install and
# waits for input, which stalls the launch. Pre-creating the credentials file
# with an empty email skips it. Never overwrite an existing one.
STREAMLIT_CRED="${HOME}/.streamlit/credentials.toml"
if [ ! -f "$STREAMLIT_CRED" ]; then
  mkdir -p "${HOME}/.streamlit"
  printf '[general]\nemail = ""\n' > "$STREAMLIT_CRED"
fi

APP_URL="http://localhost:${APP_PORT}"

echo "Launching web app..."
echo "The browser will open at ${APP_URL} once the app is ready."
echo "Close this window or press Ctrl+C to stop the app."
echo

# Open the browser once the server actually answers, rather than immediately.
(
  for _ in $(seq 1 90); do
    if curl -s -o /dev/null --max-time 2 "$APP_URL"; then
      open "$APP_URL" >/dev/null 2>&1
      exit 0
    fi
    sleep 1
  done
) &
OPENER_PID=$!

cleanup() {
  kill "$OPENER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

set +e
"$PY_CMD" -m streamlit run src/greek_med_anonymizer/web_app.py \
  --server.port="$APP_PORT" \
  --server.headless=true \
  --browser.gatherUsageStats=false
STATUS=$?
set -e

if [ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 130 ]; then
  fail "The web app stopped with an error (exit code ${STATUS}). See the messages above."
fi
