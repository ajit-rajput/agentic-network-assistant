#!/usr/bin/env python3
import random
from pathlib import Path
from datetime import datetime

OUT = Path(__file__).resolve().parents[1] / "server" / "pyats_mocks"
OUT.mkdir(parents=True, exist_ok=True)

DEVICES = [f"leaf{i}" for i in range(1,6)] + [f"spine{i}" for i in range(1,6)]

COMMANDS = [
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

def gen_if(dev):
    lines = ["Interface  IP-Address  Status  Protocol"]
    for i in range(1,5):
        ip = f"10.{random.randint(0,255)}.{random.randint(1,254)}.{random.randint(1,254)}"
        lines.append(f"Eth1/{i} {ip} up up")
    return "\n".join(lines)

def gen_bgp(dev):
    return f"""
BGP router identifier 10.0.0.{random.randint(1,254)}, local AS 65001
Neighbor        AS    Up/Down   PfxRcd
10.1.1.{random.randint(1,254)} 65002 1d02h {random.randint(1,200)}
""".strip()

def gen_version(dev):
    return f"Cisco IOS XE Software, Version 17.{random.randint(1,9)}.{random.randint(0,9)}\nDevice uptime is {random.randint(1,365)} days"

def gen_generic(dev, cmd):
    if "interface brief" in cmd:
        return gen_if(dev)
    if "bgp summary" in cmd:
        return gen_bgp(dev)
    if "version" in cmd:
        return gen_version(dev)
    return f"# Mock output for {dev} - {cmd}\n# generated {datetime.utcnow()}"

def main():
    for dev in DEVICES:
        ddir = OUT / dev
        ddir.mkdir(parents=True, exist_ok=True)
        for cmd in COMMANDS:
            fname = cmd.replace(" ", "_").replace("|","_pipe_").replace("/","_").lower()+".txt"
            (ddir / fname).write_text(gen_generic(dev, cmd))
    print("Mock pack created at:", OUT)

if __name__ == "__main__":
    main()