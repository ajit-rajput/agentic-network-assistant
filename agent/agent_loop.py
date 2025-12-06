# --- paste this into agent/agent_loop.py (replace old versions) ---
import os, json, requests, sys, re, datetime
from prompts import SYSTEM_PROMPT

TOOL_SERVER = os.environ.get("TOOL_SERVER", "http://localhost:8000")
OLLAMA_API = os.environ.get("OLLAMA_API", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

def ask_ollama(prompt):
    """Call Ollama and return the raw string content. Logs raw output for debugging."""
    url = f"{OLLAMA_API}/api/generate"
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        data = {"__ollama_error": str(e)}

    # normalize to a raw string representation
    raw = ""
    if isinstance(data, dict):
        if "response" in data:
            raw = data["response"]
        elif "choices" in data and data["choices"]:
            c0 = data["choices"][0]
            if isinstance(c0, dict):
                raw = (c0.get("message") or {}).get("content") or c0.get("text") or json.dumps(c0)
            else:
                raw = str(c0)
        else:
            raw = json.dumps(data)
    else:
        raw = str(data)

    print(f"[{datetime.datetime.utcnow().isoformat()}] OLLAMA RAW RESPONSE:\n{raw}\n---end raw---")
    return raw

def extract_json_from_text(text):
    """
    Robust JSON extractor:
    - strip leading explanation lines
    - remove Markdown code fences ``` ... ```
    - find first {...} JSON block and parse it
    - return dict or None
    """
    if not text or not isinstance(text, str):
        return None

    # remove common leading phrases like "Here is the JSON:" or "Answer:" (anything up to first newline if it doesn't start with {)
    text = text.strip()
    # Remove markdown fences ```json\n...\n``` or ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)

    # If still contains triple fenced blocks (multiple), collapse to content inside first fence
    m_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if m_fence:
        candidate = m_fence.group(1).strip()
    else:
        # remove a short leading text intro if present
        # if text does not start with '{', drop leading lines until we find a line that starts with '{'
        if not text.lstrip().startswith("{"):
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("{"):
                    candidate = "\n".join(lines[i:])
                    break
            else:
                candidate = text
        else:
            candidate = text

    candidate = candidate.strip()

    # Now try to extract the first {...} block if candidate contains extra trailing stuff
    m = re.search(r'(\{[\s\S]*?\})', candidate)
    if not m:
        return None
    json_text = m.group(1)

    # attempt to load
    try:
        return json.loads(json_text)
    except Exception:
        # attempt minor cleanup: remove trailing commas, etc (best-effort)
        cleaned = re.sub(r",\s*}", "}", json_text)
        cleaned = re.sub(r",\s*\]", "]", cleaned)
        try:
            return json.loads(cleaned)
        except Exception as e:
            print("[WARN] Failed to json.loads extracted candidate:", e)
            return None

def llm_decide_tools(user_question):
    """
    Calls Ollama, extracts JSON, validates/coerces minimal schema.
    Returns dict: {"tool": "...", "args": {...}}
    """
    prompt = SYSTEM_PROMPT + "\n\nUser: " + (user_question or "") + "\n\nRespond with the exact JSON object only."
    raw = ask_ollama(prompt)
    parsed = extract_json_from_text(raw)
    if parsed is None:
        print("[WARN] Could not parse JSON from LLM raw response. Raw below:")
        print(raw)
        # fallback heuristics: if query contains "show" and a device name, coerce to run_show
        user_lower = (user_question or "").lower()
        device_token = None
        for token in ["leaf1","leaf2","leaf3","leaf4","leaf5","spine1","spine2","spine3","spine4","spine5"]:
            if token in user_lower:
                device_token = token
                break
        wants_show = any(w in user_lower for w in ["show ", "interfaces", "interface", "bgp", "version", "running-config", "ospf", "vlan"])
        if wants_show and device_token:
            print("[INFO] Heuristic coercion to run_show:", device_token)
            return {"tool":"run_show", "args":{"device": device_token, "command":"show ip interface brief"}}
        return {"tool":"inventory", "args":{}}
    # basic validation: allow only inventory or run_show
    tool = parsed.get("tool")
    args = parsed.get("args") or {}
    if tool not in ("inventory","run_show"):
        # coerce if possible
        if "show" in (tool or "") or "device" in args:
            tool = "run_show"
        else:
            tool = "inventory"
    # ensure run_show has device and command
    if tool == "run_show":
        device = args.get("device")
        cmd = args.get("command")
        if not device or not cmd:
            # try heuristics
            user_lower = (user_question or "").lower()
            device_token = None
            for token in ["leaf1","leaf2","leaf3","leaf4","leaf5","spine1","spine2","spine3","spine4","spine5"]:
                if token in user_lower:
                    device_token = token
                    break
            if not device and device_token:
                device = device_token
            if not cmd:
                cmd = "show ip interface brief"
            # if still missing device, fallback to inventory
            if not device:
                return {"tool":"inventory","args":{}}
            return {"tool":"run_show","args":{"device": device, "command": cmd}}
    # return parsed normalized
    return {"tool": tool, "args": args}

# Ensure the main prints output clearly
def summarize_from_response(res):
    out = res.get("output","")
    lines = out.splitlines()
    return "\n".join(lines[:10])

if __name__ == "__main__":
    # simple CLI entry
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
    else:
        q = input("Ask the network agent> ").strip()
    decision = llm_decide_tools(q)
    print("DECISION:", json.dumps(decision, indent=2))
    if decision.get("tool") == "inventory":
        inv = requests.post(f"{TOOL_SERVER}/tool/inventory", json={"name": decision['args'].get("name")}).json()
        print("INVENTORY RESULT:", json.dumps(inv, indent=2))
    elif decision.get("tool") == "run_show":
        args = decision.get("args",{})
        dev = args.get("device")
        cmd = args.get("command")
        if not dev:
            print("No device specified in decision; aborting.")
            sys.exit(1)
        res = requests.post(f"{TOOL_SERVER}/tool/run_show", json={"device": dev, "command": cmd}).json()
        print("ANSWER (excerpt):")
        print(summarize_from_response(res))
        print("\nEVIDENCE:")
        print(json.dumps(res, indent=2))
    else:
        print("Unknown tool decision:", decision)