# Agentic Network Assistant

A lightweight agentic AI demo that uses a local LLM (Ollama) to decide whether to call:
- **inventory** — list devices  
- **run_show** — simulate show commands on mock network devices  

No real lab hardware is required. The backend uses pyATS-style mock outputs, and the frontend is a Streamlit UI.

---

## Features
- Local LLM reasoning via Ollama  
- Tool-based agent architecture  
- 10 mock Cisco IOS devices  
- 25+ simulated show commands  
- Streamlit web interface  
- Works completely offline  

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



****
