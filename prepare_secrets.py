import json
import os
from pathlib import Path

def prepare():
    print("\n" + "="*60)
    print("🚀 GITHUB SECRETS PREPARATION TOOL")
    print("="*60)
    print("Copy the values below into your GitHub Repository Secrets:\n")

    files = [
        ("GDRIVE_CREDENTIALS_JSON", "credentials.json"),
        ("GDRIVE_TOKEN_JSON", "token.json")
    ]

    for secret_name, filename in files:
        path = Path(filename)
        if path.exists():
            content = path.read_text()
            # Clean up whitespace
            json_str = json.dumps(json.loads(content))
            print(f"🔹 NAME: {secret_name}")
            print(f"🔹 VALUE: {json_str}\n")
        else:
            print(f"❌ {filename} not found! Skipping {secret_name}.\n")

    print("Also remember to add these standard secrets:")
    print("- GEMINI_API_KEY")
    print("- GMAIL_USER")
    print("- GMAIL_PASSWORD")
    print("- LINKEDIN_LI_AT_COOKIE")
    print("- GDRIVE_FOLDER_ID")
    print("="*60 + "\n")

if __name__ == "__main__":
    prepare()
