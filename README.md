# Agentic Network Assistant

A lightweight agentic AI demo that uses a local LLM (Ollama) to decide whether to call:
- **inventory** — list devices  
- **run_show** — simulate show commands on mock network devices  

No real lab hardware is required. The backend uses pyATS-style mock outputs, and the frontend is a Streamlit UI.

---

## Features
- Local LLM reasoning via Ollama  
- Tool-based agent architecture  
- Mock Cisco IOS devices  
- 25+ simulated show commands  
- Streamlit web interface  
- Works completely offline  

---
## Components
- Streamlit Web App
- Flask Tool Server (rest endpoints)
- Mock Data
---
## Data Flow
User Query -->
Streamlit App (LLM decision-making) -->
Ollama LLM (decides: inventory or run_show) -->
Flask Backend (executes tool, reads mock files) -->
Converts commands to filenames (e.g. show ip interface brief) -->
Results displayed in Streamlit UI
---

## Requirements
- Python 3.10+  
- Ollama installed and running  
- A model such as `llama3` pulled locally  

---

## Installation

```bash
git clone <repo-url>
cd project1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Start the Tool Server (Terminal A)
python server/tool_server.py

## Start the Application (Terminal B)
streamlit run web/streamlit_app.py

