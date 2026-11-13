#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$project_dir/python:$project_dir${PYTHONPATH:+:$PYTHONPATH}"
cert_dir="${CERTBOT_CONFIG_DIR:-/tmp/letsencrypt/config}/live/$DEVS_DOMAIN"
exec "${PYTHON_BIN:-python3}" "$project_dir/crypto_utils.py" \
    "$cert_dir/privkey.pem" "$cert_dir/privkey.pkcs1.pem"
