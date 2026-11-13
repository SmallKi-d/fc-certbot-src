#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$project_dir/python:$project_dir${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON_BIN:-python3}" "$project_dir/authenticator.py"
