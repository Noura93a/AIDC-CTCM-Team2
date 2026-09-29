# CTCM Streamlit Demo

This folder contains the Streamlit UI for the **Content Tagging & Competency Mapping (CTCM)** capstone project.

## Files

```text
demo/
├── .streamlit/
│   └── config.toml
├── streamlit_app.py
├── requirements.txt
├── run_demo.sh
└── README.md
```

## 1. Create and activate a virtual environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If the virtual environment already exists, only run:

```bash
source .venv/bin/activate
```

## 2. Install the Streamlit dependencies

From the repository root:

```bash
pip install -r demo/requirements.txt
```

## 3. Check that the backend is available

The UI uses this backend by default:

```text
http://10.0.0.15:30801
```

Check it with:

```bash
curl -m 5 http://10.0.0.15:30801/health
```

A healthy backend should return JSON similar to:

```json
{
  "status": "ok",
  "models": [
    "gpt-4o-mini",
    "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"
  ]
}
```

> During load tests or long inference requests, the health request may temporarily time out because the backend can be busy.

## 4. Start the Streamlit UI

From the repository root:

```bash
cd demo
chmod +x run_demo.sh
./run_demo.sh
```

The script starts Streamlit on:

```text
0.0.0.0:8501
```

Keep this terminal open while using the UI.

## Alternative: start Streamlit manually

```bash
cd demo
python -m streamlit run streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501
```

## 5. Change the backend URL if needed

The default backend URL is configured in `streamlit_app.py`.

You can override it without editing the code:

```bash
export CTCM_API_URL=http://10.0.0.15:30801
cd demo
./run_demo.sh
```

You can also change the endpoint from **Advanced settings** inside the Streamlit UI.

## 6. Light / Dark theme

Use the Streamlit menu in the top-right corner:

```text
⋮ → Settings → Theme
```

Available options:

- System
- Light
- Dark

Theme configuration is stored in:

```text
demo/.streamlit/config.toml
```

## 7. If port 8501 is already in use

Check which process is using the port:

```bash
ss -ltnp | grep ':8501'
```

Stop only the old Streamlit process that belongs to you, then start the app again.

If needed:

```bash
fuser -k 8501/tcp
```

Then:

```bash
cd demo
./run_demo.sh
```

## 8. If `run_demo.sh` shows Permission denied

Run:

```bash
chmod +x demo/run_demo.sh
```

Then:

```bash
cd demo
./run_demo.sh
```

## 9. Supported files

The UI accepts:

- PDF
- PPTX
- XLSX / XLS
- IPYNB
- Markdown
- TXT
- DOCX

## 10. Available models

### GPT-4o-mini
Cloud API model. It does not use the team's local GPU.

### Qwen2.5-VL-3B
Self-hosted model running on the team's GPU.

Avoid running multiple heavy Qwen tests at the same time unless concurrency/load testing is intentional.

## requirements.txt

The demo currently requires:

```text
streamlit
requests
```

Install them with:

```bash
pip install -r demo/requirements.txt
```

## Quick start

For teammates who already have the repository and Python environment:

```bash
cd ~/AIDC-CTCM-Team2
source .venv/bin/activate
pip install -r demo/requirements.txt
cd demo
chmod +x run_demo.sh
./run_demo.sh
```
