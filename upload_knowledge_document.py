from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8000"
TOKEN_PATH = Path(".knowledge_access_token")
DOCUMENT_PATH = Path("test_support_policy.txt")


def main():
    if not TOKEN_PATH.is_file():
        raise SystemExit(
            "Access token not found. Run get_knowledge_token.py first."
        )

    if not DOCUMENT_PATH.is_file():
        raise SystemExit(
            f"Knowledge document not found: {DOCUMENT_PATH.resolve()}"
        )

    token = TOKEN_PATH.read_text(encoding="utf-8").strip()

    if not token:
        raise SystemExit("The access-token file is empty.")

    with DOCUMENT_PATH.open("rb") as document_file:
        response = requests.post(
            f"{BASE_URL}/api/v1/knowledge/documents/",
            headers={
                "Authorization": f"Bearer {token}",
            },
            data={
                "title": "Test Support Policy",
                "description": (
                    "Temporary document for ingestion testing"
                ),
            },
            files={
                "file": (
                    DOCUMENT_PATH.name,
                    document_file,
                    "text/plain",
                ),
            },
            timeout=60,
        )

    print("HTTP status:", response.status_code)

    try:
        print("Response:")
        print(response.json())
    except ValueError:
        print(response.text)

    if response.status_code == 201:
        print("\nUpload succeeded. Ingestion has NOT been triggered.")
    else:
        print("\nUpload did not succeed. Investigate the response above.")


if __name__ == "__main__":
    main()
