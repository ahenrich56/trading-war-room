import paramiko
import time
import sys

host = "31.97.128.136"
port = 22
username = "root"
password = "Athena20956$"
local_zip = r"c:\Users\ant\Desktop\app\trading-war-room\new\ChatExport_2026-03-25\files\opus-trencher-bot-v3.zip"
remote_zip = "/root/opus-trencher-bot-v3.zip"
remote_dir = "/opt/opus-trencher-bot"

def run_ssh_command(ssh, cmd, timeout=120):
    """Run SSH command with timeout and output streaming."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    
    if out.strip():
        # Print last 30 lines to stay concise
        lines = out.strip().split('\n')
        if len(lines) > 30:
            print(f"  ... ({len(lines)-30} lines truncated)")
            for line in lines[-30:]:
                print(f"  {line}")
        else:
            for line in lines:
                print(f"  {line}")
    if err.strip():
        for line in err.strip().split('\n')[-10:]:
            print(f"  [ERR] {line}")
    
    print(f"  Exit code: {exit_code}")
    return exit_code, out, err

print(f"Connecting to {host}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, port, username, password, timeout=15)
    print("Connected!")

    # Step 1: Upload zip
    print("\n=== STEP 1: Uploading bot package ===")
    sftp = ssh.open_sftp()
    sftp.put(local_zip, remote_zip)
    sftp.close()
    print("Upload complete!")

    # Step 2: Install Python 3.11 (solders/solana need it)
    print("\n=== STEP 2: Installing Python 3.11 + system deps ===")
    run_ssh_command(ssh, "apt-get update -qq && apt-get install -y -qq software-properties-common unzip dos2unix", timeout=120)
    run_ssh_command(ssh, "add-apt-repository -y ppa:deadsnakes/ppa && apt-get update -qq", timeout=60)
    run_ssh_command(ssh, "apt-get install -y -qq python3.11 python3.11-venv python3.11-dev", timeout=120)

    # Step 3: Extract zip
    print("\n=== STEP 3: Extracting bot package ===")
    run_ssh_command(ssh, f"mkdir -p {remote_dir}")
    run_ssh_command(ssh, f"unzip -o {remote_zip} -d {remote_dir}")

    # Step 4: Find extracted content
    exit_code, out, _ = run_ssh_command(ssh, f"ls {remote_dir}")
    
    # The zip extracts to opus-trencher-bot/opus-trencher-bot/
    bot_dir = f"{remote_dir}/opus-trencher-bot"
    exit_code, out, _ = run_ssh_command(ssh, f"ls {bot_dir}")
    
    # Check if there's a nested directory
    if "opus-trencher-bot" in out and "main.py" not in out:
        bot_dir = f"{remote_dir}/opus-trencher-bot/opus-trencher-bot"
        run_ssh_command(ssh, f"ls {bot_dir}")

    # Step 5: Create venv with Python 3.11 and install deps
    print("\n=== STEP 5: Creating Python 3.11 venv + installing deps ===")
    
    # Create user
    run_ssh_command(ssh, "id opus-bot 2>/dev/null || useradd -r -m -s /bin/bash opus-bot")
    
    # Copy files to destination
    run_ssh_command(ssh, f"cp -r {bot_dir}/* {remote_dir}/")
    run_ssh_command(ssh, f"chown -R opus-bot:opus-bot {remote_dir}")
    
    # Create venv with python3.11
    run_ssh_command(ssh, f"sudo -u opus-bot python3.11 -m venv {remote_dir}/venv", timeout=30)
    run_ssh_command(ssh, f"sudo -u opus-bot {remote_dir}/venv/bin/pip install --upgrade pip -q", timeout=60)
    
    # Install requirements (unpin versions for python3.11 compat)
    # Write a clean requirements file
    reqs = """python-telegram-bot
python-dotenv
aiohttp
websockets
solders
solana
base58
requests
numpy
pandas
"""
    # Write requirements via echo
    run_ssh_command(ssh, f"cat > {remote_dir}/requirements.txt << 'REQEOF'\n{reqs}REQEOF")
    run_ssh_command(ssh, f"chown opus-bot:opus-bot {remote_dir}/requirements.txt")
    
    print("\n=== Installing Python packages (this may take a few minutes) ===")
    exit_code, out, err = run_ssh_command(ssh, 
        f"sudo -u opus-bot {remote_dir}/venv/bin/pip install -r {remote_dir}/requirements.txt", 
        timeout=300)
    
    if exit_code != 0:
        print("\n!!! pip install failed. Trying with --no-cache-dir...")
        run_ssh_command(ssh, 
            f"sudo -u opus-bot {remote_dir}/venv/bin/pip install --no-cache-dir -r {remote_dir}/requirements.txt", 
            timeout=300)

    # Step 6: Create systemd service
    print("\n=== STEP 6: Creating systemd service ===")
    service_content = """[Unit]
Description=OPUS Trencher Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=opus-bot
Group=opus-bot
WorkingDirectory=/opt/opus-trencher-bot
ExecStart=/opt/opus-trencher-bot/venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/opus-bot.log
StandardError=append:/var/log/opus-bot-error.log
EnvironmentFile=/opt/opus-trencher-bot/.env
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/opus-trencher-bot
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"""
    run_ssh_command(ssh, f"cat > /etc/systemd/system/opus-bot.service << 'SVCEOF'\n{service_content}SVCEOF")
    
    # Step 7: Enable and start
    print("\n=== STEP 7: Enabling and starting service ===")
    run_ssh_command(ssh, "touch /var/log/opus-bot.log /var/log/opus-bot-error.log && chown opus-bot:opus-bot /var/log/opus-bot*.log")
    run_ssh_command(ssh, "systemctl daemon-reload && systemctl enable opus-bot && systemctl restart opus-bot")
    
    # Wait a moment then check status
    time.sleep(3)
    run_ssh_command(ssh, "systemctl status opus-bot --no-pager -l")
    run_ssh_command(ssh, "tail -20 /var/log/opus-bot.log 2>/dev/null || echo 'No log yet'")

    print("\n" + "=" * 50)
    print("  DEPLOYMENT COMPLETE!")
    print("=" * 50)
    print(f"\nBot running on VPS {host}")
    print("Commands:")
    print("  systemctl status opus-bot")
    print("  systemctl restart opus-bot")
    print("  tail -f /var/log/opus-bot.log")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    ssh.close()
    print("\nDisconnected.")
