#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m pytest -q
python scripts/prepare_public_data.py
python -m lag_audit.campaign --data-root data/public --allow-incomplete --output results/reproduced-campaign
# Existing output directories are intentionally not overwritten.
# Pooling/switch scripts write fixed, new output directories; see README for reruns.
