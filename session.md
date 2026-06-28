# Session Notes — Platform Team Administration Setup

## Project Structure Created

```
platform-team-administration/
├── .circleci/
│   └── config.yml              # CircleCI pipeline with preview, update, rollback workflows
├── .env                        # Local secrets — NOT committed
├── .env.example                # Committed — shows required env vars
├── .git-hooks/
│   └── commit-msg              # Enforces Conventional Commits format
├── .gitignore
├── __main__.py                 # Pulumi entry point — defines GitHub repos with protect=True
├── Pulumi.yaml                 # Pulumi project config (uv toolchain)
├── pyproject.toml              # Python deps + pytest config
├── uv.lock
├── config/
│   └── platform_team_values.yaml   # GitHub org, repos, and members config
├── modules/
│   └── github/
├── scripts/
│   ├── install-githooks.sh     # Copies .git-hooks/ into .git/hooks/ for local use
│   ├── pulumi_repo_create.py   # Bootstrap script — creates repos, invites members, sets branch protection
│   └── sync_bw_secrets.py      # Pushes secrets-setup/*.json to Bitwarden vault
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
```

## GitHub Org

- **Org slug:** `VHRAZA`
- **Repos pushed to:** `github.com/VHRAZA/platform-team-admin` (this codebase)
- `platform-team-admin` repo is on `main` branch, pushed and tagged `v0.1.0`

## Secret Store Architecture

Bitwarden is the secret store. GitHub token is stored in `login.password` of the "GitHub Secrets" item.

```
.env (Bitwarden credentials)
  → bw unlock → BW_SESSION
    → sync_bw_secrets.py pushes github_secrets.json → Bitwarden vault
      → pulumi_repo_create.py fetches token from Bitwarden
        → GitHub API creates repos, invites members, sets branch protection
```

### Bitwarden Item Structure (github_secrets.json)

Token goes in `login.password` ONLY. The `fields` array is not used by the script.

```json
{
  "type": 1,
  "name": "GitHub Secrets",
  "login": {
    "password": "<ghp_classic_pat_token>"
  }
}
```

## GitHub Token Requirements

- Type: **Classic PAT** (`ghp_`)
- Required scopes: **`repo`** + **`admin:org`**
- Fine-grained PATs require org admin approval — avoid

## Scripts

### Working run command

```bash
set -o allexport && source .env && set +o allexport
export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)
uv run scripts/sync_bw_secrets.py   # wait for "Done: GitHub Secrets" before proceeding
uv run scripts/pulumi_repo_create.py
```

Run scripts separately — do not chain with `&&` as sync can be slow and timing out causes stale token issues.

### pulumi_repo_create.py — what it does

1. Unlocks Bitwarden, syncs vault, fetches GitHub token
2. Reads `github_org` and member/repo lists from `config/platform_team_values.yaml`
3. Invites org members by email via `POST /orgs/{org}/invitations`
4. Creates repos via `POST /orgs/{org}/repos` (skips if already exists, updates visibility)
5. Initializes each repo with a README.md commit (creates `main` branch)
6. Sets branch protection on `main` (enforce admins + require signed commits)

### install-githooks.sh

Run once after cloning to activate the commit-msg hook:

```bash
bash scripts/install-githooks.sh
```

## Repos Created (all public, VHRAZA org)

| Name | Description |
|------|-------------|
| platform-team-admin | Manages platform team membership and admin artifacts (this repo) |
| platform-core | Core platform runtime (empty — Chapter 2 starts here) |
| platform-demo-apps | Demo application for testing the platform (empty) |
| platform-extensions | Extensions for the platform (empty) |

Repos are **public** (required for branch protection on free GitHub org plan).

## Org Members

| Username | Email | Role |
|----------|-------|------|
| rcodesinjavascript | rcodesinjavascript@gmail.com | member |

## __main__.py — Pulumi Resources

All 4 repos defined as `github.Repository` resources with `protect=True` (prevents `pulumi destroy` from deleting them). Repos must be imported into Pulumi state before `pulumi up`:

```bash
pulumi stack init dev
pulumi import github:index/repository:Repository platform-team-admin platform-team-admin
pulumi import github:index/repository:Repository platform-core platform-core
pulumi import github:index/repository:Repository platform-demo-apps platform-demo-apps
pulumi import github:index/repository:Repository platform-extensions platform-extensions
```

## CircleCI Pipeline (.circleci/config.yml)

- Context: `PLATFORM_ADMIN` (set up in CircleCI — holds secrets for Pulumi jobs)
- **preview** workflow: runs `pulumi-preview` on push to `main`
- **update** workflow: runs on git tags — preview → manual approval → `pulumi-update`
- **rollback** workflow: runs on git tags — manual approval → restores previous Pulumi stack state

## Commit Signing (SSH)

Branch protection requires signed commits. Setup per developer:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_rsa.pub
git config --global commit.gpgsign true
```

Then add the key to GitHub profile as a **Signing Key** (Settings → SSH and GPG keys → New SSH key → Key type: Signing Key).

## Known Issues / Notes

- Bitwarden CLI prompts for master password interactively if vault is locked — always export `BW_SESSION` before running scripts and do NOT run `bw lock` in between
- `bw lock` invalidates `BW_SESSION` — if sync hangs, check the vault is unlocked
- Branch protection on private org repos requires GitHub Team plan (paid) — repos are public to work around this on free plan
- `platform-core` and other non-admin repos are empty — Chapter 2 begins work in `platform-core`

## Next Step

Chapter 2 — build the platform runtime codebase in `VHRAZA/platform-core`.
