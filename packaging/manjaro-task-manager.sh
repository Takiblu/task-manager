#!/usr/bin/env bash
# Launcher installed to /usr/bin/manjaro-task-manager by the PKGBUILD.
# Adds the installed library directory to PYTHONPATH and execs main.py
# so `src.*` absolute imports used throughout the codebase resolve
# correctly regardless of the caller's working directory.
set -euo pipefail

APP_LIB_DIR="/usr/lib/manjaro-task-manager"

exec env PYTHONPATH="${APP_LIB_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 "${APP_LIB_DIR}/src/main.py" "$@"
