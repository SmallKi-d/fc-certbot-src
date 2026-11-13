#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "${PYTHON_BIN:-}" ]; then
    python_bin="$PYTHON_BIN"
elif command -v python3.12 >/dev/null 2>&1; then
    python_bin="python3.12"
elif [ -x /usr/local/envs/py312/bin/python3 ]; then
    python_bin="/usr/local/envs/py312/bin/python3"
else
    python_bin="python3"
fi
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Build dependencies with Python 3.12"'
build_dir="$(mktemp -d "$project_dir/.python-build.XXXXXX")"
trap 'rm -rf -- "$build_dir"' EXIT
index_url="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
"$python_bin" -m pip install --index-url "$index_url" --target "$build_dir" -r "$project_dir/requirements.txt"
if [ -d "$project_dir/python" ]; then
    backup_dir="$(mktemp -d "${TMPDIR:-/tmp}/cert-generator-python-backup.XXXXXX")"
    mv -- "$project_dir/python" "$backup_dir/python"
    echo "Previous dependencies saved to $backup_dir/python"
fi
mv -- "$build_dir" "$project_dir/python"
echo "Python 3.12 dependencies installed in $project_dir/python"
