#!/bin/bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for TASK_ENV in "$TASK_ROOT/build-the-builder/env.sh" "$TASK_ROOT/build-the-builder/.env" "$TASK_ROOT/.env"; do
  if [[ -f "$TASK_ENV" ]]; then
    set -a
    source "$TASK_ENV"
    set +a
    break
  fi
done
TASK_PYTHONS=()
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  TASK_PYTHONS+=("$VIRTUAL_ENV/bin/python")
fi
TASK_PYTHONS+=(/opt/homebrew/bin/python3 python3 python)
for TASK_PYTHON in "${TASK_PYTHONS[@]}"; do
  if command -v "$TASK_PYTHON" >/dev/null 2>&1 && "$TASK_PYTHON" -c 'import sys;sys.exit(sys.version_info < (3,10))'; then
    cd "$TASK_ROOT"
    exec "$TASK_PYTHON" "$TASK_ROOT/scripts/build_agent.py" "$@"
  fi
done
echo 'Python 3.10 or newer is required.' >&2
exit 2
