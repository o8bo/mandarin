#!/usr/bin/env bash
set -euo pipefail
MANDARIN_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$MANDARIN_ROOT/vendor:$MANDARIN_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$MANDARIN_ROOT/vendor/usr/bin:$MANDARIN_ROOT/vendor/bin:$PATH"
exec /usr/bin/python3 -m mandarin "$@"
