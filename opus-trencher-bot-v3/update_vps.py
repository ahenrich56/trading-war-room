import paramiko
import os

host = "31.97.128.136"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, 22, "root", "Athena20956$", timeout=15)

# Upload updated files to VPS
sftp = ssh.open_sftp()
local_dir = r"c:\Users\ant\Desktop\app\trading-war-room\opus-trencher-bot-v3\opus-trencher-bot"
remote_dir = "/opt/opus-trencher-bot"

def put_dir(sftp, local_dir, remote_dir):
    """Recursively upload a directory to VPS."""
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass # Directory already exists
    
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        if os.path.isfile(local_path):
            print(f"Uploading {item}...")
            sftp.put(local_path, remote_path)
        elif os.path.isdir(local_path):
            put_dir(sftp, local_path, remote_path)

files_to_update = ["database.py", "main.py", "dashboard_api.py", "requirements.txt"]

for f in files_to_update:
    local_path = os.path.join(local_dir, f)
    remote_path = f"{remote_dir}/{f}"
    print(f"Uploading {f}...")
    sftp.put(local_path, remote_path)

# Upload dashboard directory
print("Uploading dashboard directory...")
put_dir(sftp, os.path.join(local_dir, "dashboard"), f"{remote_dir}/dashboard")

sftp.close()
print("Files uploaded!")

# Fix ownership
stdin, stdout, stderr = ssh.exec_command(f"chown -R opus-bot:opus-bot {remote_dir}")
stdout.read()

# Open port 8420 in firewall
print("Opening port 8420...")
stdin, stdout, stderr = ssh.exec_command("ufw allow 8420/tcp 2>/dev/null; iptables -I INPUT -p tcp --dport 8420 -j ACCEPT 2>/dev/null; echo done")
print(stdout.read().decode())

# Delete old WAL/SHM files to fix any stale locks
print("Cleaning stale DB locks...")
stdin, stdout, stderr = ssh.exec_command(f"rm -f {remote_dir}/opus_bot.db-shm {remote_dir}/opus_bot.db-wal; chown opus-bot:opus-bot {remote_dir}/opus_bot.db 2>/dev/null; echo done")
print(stdout.read().decode())

# Restart service
print("Restarting bot service...")
stdin, stdout, stderr = ssh.exec_command("systemctl restart opus-bot")
stdout.read()

import time
time.sleep(4)

# Check status
stdin, stdout, stderr = ssh.exec_command("systemctl is-active opus-bot")
status = stdout.read().decode().strip()
print(f"Service status: {status}")

# Check dashboard API
stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8420/api/health 2>/dev/null || echo 'API not ready yet'")
health = stdout.read().decode().strip()
print(f"Dashboard API: {health}")

# Check latest log
stdin, stdout, stderr = ssh.exec_command(f"grep -i 'dashboard' /var/log/opus-bot.log 2>/dev/null | tail -3")
log_out = stdout.read().decode().strip()
if log_out:
    print(f"Dashboard log: {log_out}")

ssh.close()
print("\nDone! Bot restarted with dashboard API on port 8420")
