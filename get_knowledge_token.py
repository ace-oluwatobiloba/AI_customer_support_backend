import getpass
from pathlib import Path

import requests

base_url = "http://127.0.0.1:8000"

email = input("Administrator email: ").strip()
password = getpass.getpass("Administrator password: ")

try:
    response = requests.post(
        f"{base_url}/api/v1/auth/token/",
        json={
            "email": email,
            "password": password,
        },
        timeout=30,
    )
except requests.RequestException as exc:
    raise SystemExit(f"Could not contact Django: {exc}")

print("HTTP status:", response.status_code)

if response.status_code != 200:
    print("Response:", response.text)
    raise SystemExit("JWT authentication failed.")

payload = response.json()
access_token = payload.get("access")

if not access_token:
    print("Response keys:", list(payload.keys()))
    raise SystemExit("No access token was returned.")

Path(".knowledge_access_token").write_text(
    access_token,
    encoding="utf-8",
)

print("Access token saved successfully.")
print("Token value intentionally not displayed.")
