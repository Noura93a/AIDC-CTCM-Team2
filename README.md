# \# Content Tagging \& Competency Mapping

# 

# \## Clone

# git clone https://github.com/Noura93a/AIDC-CTCM-Team2.git

# 

# \## Setup

# cd AIDC-CTCM-Team2/app

# python3 -m venv .venv \&\& source .venv/bin/activate

# pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121

# pip install -r requirements.txt

# 

# \## Env vars

# export OPENAI\_API\_KEY=sk-...

# export OPENAI\_MODEL=gpt-4o-mini

# export SKILLS\_CSV\_PATH=\~/AIDC-CTCM-Team2/data/hrsd\_data\_ai\_taxonomy.csv

# export GOLD\_SET\_PATH=\~/AIDC-CTCM-Team2/data/Golden-set-Reviewed.xlsx

# 

# \## Start server

# uvicorn main:app --host 0.0.0.0 --port 8000

# 

# \## Test

# cd \~/AIDC-CTCM-Team2

# python evaluation/run\_benchmark.py \\

# &#x20; --server http://localhost:8000 \\

# &#x20; --data-dir ./data \\

# &#x20; --gold ./data/Golden-set-Reviewed.xlsx \\

# &#x20; --models openai \\

# &#x20; --out ./test\_results

