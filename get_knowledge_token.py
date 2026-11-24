import getpass
from pathlib import Path

import requests


BASE_URL = "http://127.0.0.1:8000"
PROJECT_ROOT = Path(__file__).resolve().parent
TOKEN_DIR = PROJECT_ROOT / ".secrets"
TOKEN_PATH = TOKEN_DIR / "knowledge_access_token"


def main():
    email = input("Administrator email: ").strip()
    password = getpass.getpass("Administrator password: ")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/token/",
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

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(access_token, encoding="utf-8")

    print("Access token saved successfully.")
    print("Token value intentionally not displayed.")
    print("Token location:", TOKEN_PATH)


if __name__ == "__main__":
    main()
