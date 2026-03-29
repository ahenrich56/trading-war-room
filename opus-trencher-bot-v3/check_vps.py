import paramiko
import requests

vps_ip = "31.97.128.136"
api_port = 4000

print(f"Checking VPS {vps_ip} on port {api_port}...")

# 1. Local check (via SSH)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(vps_ip, 22, "root", "Athena20956$", timeout=15)

cmds = [
    ("Service", "systemctl is-active opus-bot"),
    ("Health API (Local)", f"curl -s http://localhost:{api_port}/api/health"),
    ("Status API (Local)", f"curl -s http://localhost:{api_port}/api/status | head -c 500"),
]

with open("vps_api_check.txt", "w", encoding="utf-8") as f:
    for label, cmd in cmds:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode('utf-8', errors='replace')
        f.write(f"=== {label} ===\n{out}\n\n")

    # 2. Remote check (Direct)
    f.write("=== Remote Accessibility ===\n")
    try:
        resp = requests.get(f"http://{vps_ip}:{api_port}/api/health", timeout=10)
        f.write(f"Direct connection: SUCCESS (Status {resp.status_code})\n")
    except Exception as e:
        f.write(f"Direct connection: FAILED ({str(e)})\n")

ssh.close()
print("Done - see vps_api_check.txt")
