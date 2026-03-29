import requests

vps_ip = "31.97.128.136"

print(f"Checking Nginx Reverse Proxy on {vps_ip}...")

# 1. Health check via port 80 /opus-api/
try:
    resp = requests.get(f"http://{vps_ip}/opus-api/health", timeout=10)
    print(f"Nginx /opus-api/health: SUCCESS (Status {resp.status_code})")
    print(resp.text)
except Exception as e:
    print(f"Nginx /opus-api/health: FAILED ({str(e)})")

# 2. Dashboard check via port 80 /opus/
try:
    resp = requests.get(f"http://{vps_ip}/opus/", timeout=10)
    print(f"Nginx /opus/: SUCCESS (Status {resp.status_code})")
except Exception as e:
    print(f"Nginx /opus/: FAILED ({str(e)})")
