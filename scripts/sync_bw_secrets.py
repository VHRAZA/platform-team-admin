import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], input: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=input,
        capture_output=True,
        text=True,
    )


def main():
    session = os.environ.get("BW_SESSION")
    if not session:
        print("BW_SESSION is not set. Run 'bw unlock' and export the session token.")
        sys.exit(1)

    secrets_dir = Path(__file__).parent.parent / "secrets-setup"
    json_files = list(secrets_dir.glob("*.json"))

    if not json_files:
        print(f"No .json files found in {secrets_dir}")
        sys.exit(0)

    for json_file in json_files:
        print(f"Processing: {json_file.name}")
        item_name = json.loads(json_file.read_text())["name"]

        existing = run(["bw", "get", "item", item_name, "--session", session])
        raw = json_file.read_text()

        encoded = run(["bw", "encode"], input=raw)
        if encoded.returncode != 0:
            print(f"  Failed to encode {json_file.name}: {encoded.stderr}")
            continue

        if existing.returncode == 0 and existing.stdout.strip():
            item_id = json.loads(existing.stdout)["id"]
            print(f"  '{item_name}' exists — updating (id: {item_id})")
            result = run(["bw", "edit", "item", item_id, "--session", session], input=encoded.stdout)
        else:
            print(f"  '{item_name}' not found — creating")
            result = run(["bw", "create", "item", "--session", session], input=encoded.stdout)

        if result.returncode == 0:
            print(f"  Done: {item_name}")
        else:
            print(f"  Error: {result.stderr}")


if __name__ == "__main__":
    main()
