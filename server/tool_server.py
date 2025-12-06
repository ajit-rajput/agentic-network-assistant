from flask import Flask, request, jsonify
from pathlib import Path

app = Flask(__name__)
BASE = Path(__file__).parent
MOCK_DIR = BASE / "pyats_mocks"

ALLOWED_COMMANDS = {
    "cisco_ios": [
        "show ip interface brief",
        "show version",
        "show ip bgp summary",
        "show running-config",
        "show interfaces status",
        "show processes cpu",
        "show logging",
        "show ip route",
        "show arp",
        "show ntp status",
        "show inventory",
        "show platform",
        "show controllers",
        "show ip ospf neighbor",
        "show mac address-table",
        "show vlan brief",
        "show ip interface",
        "show users",
        "show clock",
        "show ip cef",
        "show tacacs",
        "show startup-config",
        "show running-config | include interface",
        "show license",
        "show version | include uptime"
    ]
}

def _list_devices():
    if not MOCK_DIR.exists():
        return []
    return [p.name for p in MOCK_DIR.iterdir() if p.is_dir()]

@app.route("/tool/inventory", methods=["POST"])
def inventory_tool():
    body = request.json or {}
    name = body.get("name")
    devices = _list_devices()
    if name:
        if name in devices:
            return jsonify({"ok": True, "result": [{"name": name, "vendor": "cisco_ios"}]})
        return jsonify({"ok": False, "error": "device not found"}), 404

    return jsonify({"ok": True, "result": [{"name": d, "vendor": "cisco_ios"} for d in devices]})

def _cmd_to_file(cmd):
    return cmd.replace(" ", "_").replace("|","_pipe_").replace("/", "_").lower() + ".txt"

@app.route("/tool/run_show", methods=["POST"])
def run_show():
    body = request.json or {}
    device = body.get("device")
    command = body.get("command", "").strip()

    if not device or not command:
        return jsonify({"ok": False, "error": "device and command required"}), 400

    if command not in ALLOWED_COMMANDS["cisco_ios"]:
        return jsonify({"ok": False, "error": "command not allowed"}), 403

    ddir = MOCK_DIR / device
    if not ddir.exists():
        return jsonify({"ok": False, "error": "device not found"}), 404

    fname = _cmd_to_file(command)
    fpath = ddir / fname

    if not fpath.exists():
        return jsonify({"ok": False, "error": f"mock file not found: {fname}"}), 404

    output = fpath.read_text()

    return jsonify({
        "ok": True,
        "device": device,
        "command": command,
        "output": output
    })

if __name__ == "__main__":
    app.run(host="localhost", port=8000)