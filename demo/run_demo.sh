#!/usr/bin/env bash
set -e

# Always run from the demo directory so Streamlit reads:
# demo/.streamlit/config.toml
cd "$(dirname "$0")"

python -m streamlit run streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501
