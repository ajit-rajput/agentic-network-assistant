# web/streamlit_app.py
import os
import json
import requests
import streamlit as st
import re
from datetime import datetime

# Config from env (when running locally set TOOL_SERVER=http://localhost:8000)
TOOL_SERVER = os.environ.get("TOOL_SERVER", "http://localhost:8000")
OLLAMA_API = os.environ.get("OLLAMA_API", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

SYSTEM_PROMPT = """
You are a careful network assistant. You may call:
- inventory tool: POST /tool/inventory with {"name": "<optional device name>"}
- run_show: POST /tool/run_show with {"device": "<name>", "command": "<allowed command>"}

Rules:
- Return ONLY a single JSON object when asked which tool to call.
- The JSON must be exactly one of:
  {"tool":"inventory","args":{"name": null}}
  {"tool":"run_show","args":{"device":"leaf1","command":"show ip interface brief"}}
- If the user mentions a device (e.g., leaf1) and a show-like verb, prefer run_show.
"""

# -----------------------
# Helpers: Ollama, extractor, heuristics
# -----------------------
def ask_ollama_raw(prompt):
    """Call Ollama and return raw text content (string)."""
    try:
        resp = requests.post(f"{OLLAMA_API}/api/generate",
                             json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                             timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"[ERROR] Ollama call failed: {e}"

    # try common shapes
    if isinstance(data, dict):
        if "response" in data:
            return data["response"]
        if "choices" in data and data["choices"]:
            c0 = data["choices"][0]
            if isinstance(c0, dict):
                # some Ollama shapes: {'message':{'content':...}} or {'text':...}
                msg = (c0.get("message") or {}).get("content") if isinstance(c0.get("message"), dict) else None
                return msg or c0.get("text") or json.dumps(c0)
    return str(data)

def extract_json_from_text(text):
    """
    Robust extractor to find JSON object inside free text or fenced markdown.
    Returns dict or None.
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip()
    # remove triple-backtick blocks and capture inside if present
    m_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, flags=re.IGNORECASE)
    if m_fence:
        candidate = m_fence.group(1).strip()
    else:
        # if intro lines exist, find first line that starts with '{'
        if not t.lstrip().startswith("{"):
            lines = t.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("{"):
                    candidate = "\n".join(lines[i:]).strip()
                    break
            else:
                candidate = t
        else:
            candidate = t

    # find first {...} block
    m = re.search(r'(\{[\s\S]*?\})', candidate)
    if not m:
        return None
    json_text = m.group(1)
    # attempt load; do small cleanups if necessary
    try:
        return json.loads(json_text)
    except Exception:
        cleaned = re.sub(r",\s*}", "}", json_text)
        cleaned = re.sub(r",\s*\]", "]", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            return None

def heuristics_coerce(parsed, user_question):
    """Ensure parsed decision is valid; coerce to run_show if user clearly asks for it."""
    user_lower = (user_question or "").lower()
    # detect device tokens
    device_token = None
    for token in ["leaf1","leaf2","leaf3","leaf4","leaf5","spine1","spine2","spine3","spine4","spine5"]:
        if token in user_lower:
            device_token = token
            break
    wants_show = any(w in user_lower for w in ["show ", "interfaces", "interface", "bgp", "version", "running-config", "ospf", "vlan", "mac address"])
    if not isinstance(parsed, dict):
        parsed = {"tool":"inventory","args":{}}
    tool = parsed.get("tool")
    args = parsed.get("args") or {}

    # Normalize tool
    if tool not in ("inventory","run_show"):
        # try inference
        if "show" in (tool or "") or "device" in args:
            tool = "run_show"
        else:
            tool = "inventory"

    if tool == "run_show":
        device = args.get("device") or device_token
        cmd = args.get("command") or "show ip interface brief"
        if not device:
            # fallback to inventory if no device could be inferred
            return {"tool":"inventory","args":{}}
        return {"tool":"run_show","args":{"device": device, "command": cmd}}

    # If model chose inventory but the user clearly wants a show on a device, coerce
    if tool == "inventory" and wants_show and device_token:
        return {"tool":"run_show","args":{"device": device_token, "command": "show ip interface brief"}}

    return {"tool":"inventory","args": {"name": args.get("name") if args.get("name") else None}}

# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(page_title="Project1 - Network Agent", layout="wide")
st.title("Project 1 — Agentic Network Assistant (Streamlit)")

# Sidebar
st.sidebar.header("Controls & Debug")
st.sidebar.markdown(f"**Tool server:** {TOOL_SERVER}")
st.sidebar.markdown(f"**Ollama API:** {OLLAMA_API}")
force_run_show = st.sidebar.checkbox("Force run_show (bypass LLM)", value=False)
show_raw_llm = st.sidebar.checkbox("Show raw LLM response", value=True)

# device list preview
try:
    inv = requests.post(f"{TOOL_SERVER}/tool/inventory", json={}, timeout=6).json()
    devices = [d["name"] for d in inv.get("result", [])] if inv.get("ok") else []
except Exception:
    devices = ["leaf1","leaf2","leaf3","leaf4","leaf5","spine1","spine2","spine3","spine4","spine5"]
st.sidebar.markdown("**Detected devices:** " + ", ".join(devices))

sample_queries = [
    "List all devices",
    "Show ip interface brief on leaf1",
    "Show ip bgp summary on leaf2",
    "Show version on spine3",
    "Show running-config on leaf4"
]
if st.sidebar.button("Fill sample query"):
    st.session_state['user_query'] = sample_queries[0]

# Main area
user_query = st.text_input("Ask the network agent (example: 'Show ip interface brief on leaf1')", key="user_query")

# When user submits
if st.button("Send") or (user_query and st.session_state.get('user_query') == user_query):
    q = (user_query or "").strip()
    if not q:
        st.warning("Type a question first.")
    else:
        st.info(f"Query submitted: {q}")
        # determine decision: either force or LLM-based
        if force_run_show:
            decision = {"tool":"run_show","args":{"device": devices[0] if devices else "leaf1", "command":"show ip interface brief"}}
            st.sidebar.success("DEBUG: forced run_show")
        else:
            prompt = SYSTEM_PROMPT + "\n\nUser: " + q + "\n\nRespond with the exact JSON object only."
            raw = ask_ollama_raw(prompt)
            if show_raw_llm:
                st.sidebar.subheader("LLM raw response")
                st.sidebar.code(raw[:4000])
            parsed = extract_json_from_text(raw)
            final_decision = heuristics_coerce(parsed, q)
            decision = final_decision
            st.sidebar.subheader("LLM decision (after extraction & coercion)")
            st.sidebar.code(json.dumps(decision, indent=2))

        # execute the tool
        tool = decision.get("tool")
        args = decision.get("args", {})

        if tool == "inventory":
            try:
                res = requests.post(f"{TOOL_SERVER}/tool/inventory", json={"name": args.get("name")}, timeout=10).json()
                if res.get("ok"):
                    st.success("Inventory result")
                    st.json(res)
                else:
                    st.error("Inventory error: " + str(res.get("error")))
            except Exception as e:
                st.error("Error calling inventory: " + str(e))
        elif tool == "run_show":
            dev = args.get("device")
            cmd = args.get("command")
            if not dev:
                st.error("No device specified in decision.")
            else:
                try:
                    resp = requests.post(f"{TOOL_SERVER}/tool/run_show", json={"device": dev, "command": cmd}, timeout=20)
                    st.sidebar.write("HTTP status:", resp.status_code)
                    try:
                        res = resp.json()
                    except Exception as e:
                        st.error("Failed to parse tool_server response as JSON: " + str(e))
                        st.code(resp.text[:2000])
                        res = {"ok": False, "error": "invalid json"}
                    if not res.get("ok"):
                        st.error("Tool error: " + str(res.get("error")))
                    else:
                        st.success(f"Command executed on {dev}")
                        st.subheader("Short summary")
                        out = res.get("output","")
                        st.code("\n".join(out.splitlines()[:20]))
                        with st.expander("Full evidence (raw JSON)"):
                            st.json(res)
                except Exception as e:
                    st.error("Request to tool_server failed: " + str(e))
        else:
            st.error("Unknown tool returned by LLM: " + str(tool))