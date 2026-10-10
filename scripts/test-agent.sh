#!/bin/bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
for TASK_ENV in "$TASK_ROOT/build-the-builder/env.sh" "$TASK_ROOT/build-the-builder/.env" "$TASK_ROOT/.env"; do
  if [[ -f "$TASK_ENV" ]]; then
    source "$TASK_ENV"
    break
  fi
done
set +a
for TASK_PYTHON in /opt/homebrew/bin/python3 python3 python; do
  if command -v "$TASK_PYTHON" >/dev/null 2>&1 && "$TASK_PYTHON" -c 'import sys;sys.exit(sys.version_info < (3,10))'; then
    cd "$TASK_ROOT/build-the-builder"
    exec "$TASK_PYTHON" "$TASK_ROOT/scripts/test_agent.py" "$@"
  fi
done
echo 'Python 3.10 or newer is required.' >&2
exit 2
