import json
import os
import subprocess
import urllib.error
import urllib.request
import yaml
from pathlib import Path


def bw_run(cmd: list[str], input: str = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, input=input)
    if result.returncode != 0:
        raise RuntimeError(f"bw error: {result.stderr.strip()}")
    return result.stdout.strip()


def get_bw_session() -> str:
    status = json.loads(bw_run(["bw", "status"]))["status"]
    if status == "unauthenticated":
        bw_run(["bw", "login", "--apikey"])
    return bw_run(["bw", "unlock", "--passwordenv", "BW_PASSWORD", "--raw"])



def get_field(item: dict, field_name: str) -> str:
    for f in item.get("fields", []):
        if f["name"] == field_name:
            return f["value"]
    raise KeyError(f"Field '{field_name}' not found in Bitwarden item")


def invite_org_member(token: str, org: str, email: str, role: str = "direct_member") -> dict:
    url = f"https://api.github.com/orgs/{org}/invitations"
    payload = json.dumps({"email": email, "role": role}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 422 and "already_invited" in body:
            return None
        raise RuntimeError(f"GitHub API error {e.code}: {body}")


def initialize_repo(token: str, org: str, repo: str) -> None:
    import base64
    url = f"https://api.github.com/repos/{org}/{repo}/contents/README.md"
    content = base64.b64encode(f"# {repo}\n".encode()).decode()
    payload = json.dumps({"message": "Initial commit", "content": content}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        if e.code != 422:
            raise


def set_branch_protection(token: str, org: str, repo: str, branch: str = "main") -> None:
    base = f"https://api.github.com/repos/{org}/{repo}/branches/{branch}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    protection_payload = json.dumps({
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
    }).encode()
    req = urllib.request.Request(
        f"{base}/protection",
        data=protection_payload,
        headers=headers,
        method="PUT",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()

    sig_req = urllib.request.Request(
        f"{base}/protection/required_signatures",
        data=b"{}",
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(sig_req) as resp:
        resp.read()


def create_github_repo(token: str, org: str, name: str, description: str, visibility: str) -> dict:
    url = f"https://api.github.com/orgs/{org}/repos"
    payload = json.dumps({
        "name": name,
        "description": description,
        "private": visibility != "public",
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 422 and "already exists" in body:
            return None
        raise RuntimeError(f"GitHub API error {e.code}: {body}")


def update_github_repo(token: str, org: str, name: str, visibility: str) -> None:
    url = f"https://api.github.com/repos/{org}/{name}"
    payload = json.dumps({"private": visibility != "public"}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


session = get_bw_session()
bw_run(["bw", "sync", "--session", session])
item = json.loads(bw_run(["bw", "get", "item", "GitHub Secrets", "--session", session]))

github_token = item["login"]["password"]

with open(Path(__file__).parent.parent / "config" / "platform_team_values.yaml") as f:
    data = yaml.safe_load(f)


# Token requires scopes: repo, admin:org
github_org = data["github_org"]
print(f"Using GitHub org: {github_org}")

for member in data.get("github_organization_members", []):
    email = member["email"]
    gh_role = "admin" if member.get("github-role", "").lower() == "admin" else "direct_member"
    print(f"Inviting org member: {email}")
    result = invite_org_member(github_token, github_org, email, gh_role)
    if result is None:
        print(f"  Skipped: already invited")
    else:
        print(f"  Invited: {email}")

for repo_def in data.get("github_repositories", []):
    repo_name = repo_def.get("name")
    repo_description = repo_def.get("description", "")
    visibility = repo_def.get("visibility", "private")

    print(f"Creating repo: {repo_name}")
    result = create_github_repo(github_token, github_org, repo_name, repo_description, visibility)
    if result is None:
        print(f"  Skipped: already exists — updating visibility")
        update_github_repo(github_token, github_org, repo_name, visibility)
    else:
        print(f"  Created: {result.get('html_url')}")
    initialize_repo(github_token, github_org, repo_name)
    try:
        set_branch_protection(github_token, github_org, repo_name)
        print(f"  Branch protection set on main")
    except (RuntimeError, urllib.error.HTTPError) as e:
        print(f"  Branch protection skipped: {e}")