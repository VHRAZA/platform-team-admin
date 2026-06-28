# Session Notes — Platform Team Administration Setup

## Project Structure Created

```
platform-team-administration/
├── .circleci/
├── .env                        # Local secrets — NOT committed
├── .env.example                # Committed — shows required env vars
├── .gitignore
├── __main__.py                 # Pulumi entry point (currently empty)
├── Pulumi.yaml                 # Pulumi project config (uv toolchain)
├── pyproject.toml              # Python deps + pytest config
├── uv.lock
├── config/
│   └── platform_team_values.yaml   # GitHub repos to create
├── modules/
│   └── github/
├── scripts/
│   ├── pulumi_repo_create.py   # One-time script to bootstrap GitHub repos
│   ├── sync_bw_secrets.py      # One-time script to push secrets to Bitwarden
│   └── platform_team_values.yaml  # (moved to config/)
├── secrets-setup/
│   ├── github_secrets.json         # Real secrets — NOT committed
│   └── github_secrets.json_example # Committed — shows Bitwarden item structure
└── tests/
    ├── __init__.py
    └── test_stack.py
```

## Environment Variables (.env)

```
BW_CLIENTID=        # Bitwarden API key client ID
BW_CLIENTSECRET=    # Bitwarden API key client secret
BW_PASSWORD=        # Bitwarden master password
GITHUB_TOKEN=       # Not used — token comes from Bitwarden at runtime
GITHUB_OWNER=       # Not used — owner comes from Bitwarden at runtime
```

## Secret Store Architecture

Bitwarden is the secret store. GitHub credentials are stored as a Bitwarden Login item with custom fields — not in `.env` or Pulumi config.

```
.env (Bitwarden credentials)
  → bw unlock → BW_SESSION
    → sync_bw_secrets.py pushes github_secrets.json → Bitwarden vault
      → pulumi_repo_create.py fetches token + owner from Bitwarden
        → GitHub API creates repositories
```

### Bitwarden Item Structure (github_secrets.json)

```json
{
  "type": 1,
  "name": "GitHub Secrets",
  "notes": "Bitwarden Secrets for Pulumi GitHub provider",
  "fields": [
    { "name": "pulumi-github-token", "value": "<ghp_token>", "type": 0 },
    { "name": "pulumi-github-owner", "value": "<org_name>", "type": 0 }
  ],
  "login": {
    "uris": [], "username": null, "password": "add pwd here",
    "totp": null, "passwordRevisionDate": null
  }
}
```

## Scripts

### sync_bw_secrets.py
Reads all `*.json` files from `secrets-setup/`, checks if each item exists in
Bitwarden by name, then creates or updates it.

```bash
set -o allexport && source .env && set +o allexport
export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)
uv run scripts/sync_bw_secrets.py
```

### pulumi_repo_create.py
One-time bootstrap script. Unlocks Bitwarden, fetches GitHub token and org from
the vault, then calls the GitHub API to create each repo defined in
`config/platform_team_values.yaml`.

```bash
set -o allexport && source .env && set +o allexport
uv run scripts/pulumi_repo_create.py
```

### Repos to Create (platform_team_values.yaml)

| Name | Description | Visibility |
|------|-------------|------------|
| platform-team-admin | Manage platform team membership and admin artifacts | private |
| platform-core | Core platform runtime | private |
| platform-demo-apps | Demo application for testing the platform | private |

## GitHub Token Requirements

- Type: **Classic PAT** (starts with `ghp_`)
- Required scope: **`repo`** only
- Fine-grained PATs (`github_pat_`) require org admin approval — avoid for now

## GitHub Repo Creation — RESOLVED

### What was tried and root causes found

1. Initially `pulumi.Config("github").require("token")` was used — failed because
   Pulumi config was never set. Switched to reading from Bitwarden instead.
2. Fine-grained PAT (`github_pat_`) was used first — GitHub requires org admin
   approval for these. Switched to classic PAT (`ghp_`).
3. `pulumi_repo_create.py` was reading token from custom `fields` array
   (`get_field(item, "pulumi-github-token")`), but the book/design stores the
   token in `login.password`. The `fields` array still had placeholder values so
   the GitHub API always received `"your_github_pat_token"` → 401/403.
4. Script was hitting `/orgs/{owner}/repos` but this is a personal account — the
   correct endpoint is `/user/repos` (no owner needed).
5. Bitwarden local cache issue: `bw get` reads stale cache without a `bw sync`
   first. Added `bw sync` inside `pulumi_repo_create.py` after `get_bw_session()`.

### Fixes applied to pulumi_repo_create.py
- Read token from `item["login"]["password"]` instead of custom fields
- API endpoint changed from `/orgs/{owner}/repos` to `/user/repos`
- `bw sync` called automatically after `get_bw_session()` before any vault reads
- Removed `get_field()` helper (no longer needed)
- Removed debug print line

### Secret structure (github_secrets.json)
Token goes in `login.password` only. The `fields` array is not used by the script.
`username`, `totp`, `uris`, `passwordRevisionDate` all left as null/empty.

### Working run command
```bash
set -o allexport && source .env && set +o allexport
export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)
uv run scripts/sync_bw_secrets.py
uv run scripts/pulumi_repo_create.py
```

### Repos created
- `platform-team-admin`
- `platform-core`
- `platform-demo-apps`

## Pulumi Setup Notes

- Backend: Pulumi Cloud (ephemeral account created during `pulumi new`)
- Claim URL was generated — claim at app.pulumi.com before expiry
- Toolchain: uv (not pip/venv)
- Stack: not yet initialized (`pulumi stack init dev` needed before `pulumi up`)
- `__main__.py` is currently empty — Pulumi infrastructure code will go here

## Testing

```bash
uv run pytest          # runs tests/test_stack.py
```

Stop hook runs `uv run pytest` automatically after each session.
