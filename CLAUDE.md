# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

Manages the VHRAZA GitHub org — creates repos, invites members, sets branch protection, and tracks those resources in Pulumi. This is Chapter 1 of the platform engineering book. Chapter 2 lives in `VHRAZA/platform-core`.

## Commands

```bash
# Install deps
uv sync

# Unlock Bitwarden and export session (always do this first)
set -o allexport && source .env && set +o allexport
export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)

# Push secrets to Bitwarden vault (wait for "Done: GitHub Secrets" before running next script)
uv run scripts/sync_bw_secrets.py

# Bootstrap GitHub org — create repos, invite members, set branch protection
uv run scripts/pulumi_repo_create.py

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_stack.py::test_placeholder

# Install git commit-msg hook (run once after cloning)
bash scripts/install-githooks.sh
```

## Architecture

**Secret flow:**
```
.env (Bitwarden credentials)
  → BW_SESSION
    → secrets-setup/github_secrets.json → Bitwarden vault (sync_bw_secrets.py)
      → GitHub token fetched from Bitwarden login.password
        → GitHub API: repos created, members invited, branch protection set (pulumi_repo_create.py)
```

**Config-driven:** `config/platform_team_values.yaml` is the single source of truth for org name, repo definitions, and member list. Both bootstrap scripts read from it.

**Pulumi (`__main__.py`)** declares the same 4 repos as `github.Repository` resources with `protect=True`. The repos already exist on GitHub — they must be imported before `pulumi up` will work:

```bash
pulumi stack init dev
pulumi import github:index/repository:Repository platform-team-admin platform-team-admin
pulumi import github:index/repository:Repository platform-core platform-core
pulumi import github:index/repository:Repository platform-demo-apps platform-demo-apps
pulumi import github:index/repository:Repository platform-extensions platform-extensions
```

**CircleCI (`.circleci/config.yml`)** uses the `PLATFORM_ADMIN` context with three workflows:
- `preview` — runs on push to `main`
- `update` — runs on git tag, requires manual approval before `pulumi up`
- `rollback` — runs on git tag, restores previous Pulumi stack state

## Key constraints

- **Run scripts separately** — do not chain `sync_bw_secrets.py` and `pulumi_repo_create.py` with `&&`. Sync is slow; a stale `BW_SESSION` between runs breaks the second script.
- **Classic PAT only** — fine-grained PATs require org admin approval in VHRAZA. Token needs `repo` + `admin:org` scopes, stored in Bitwarden item `"GitHub Secrets"` under `login.password`.
- **Repos must be public** — branch protection on private repos requires GitHub Team plan (paid). VHRAZA is on the free plan.
- **Signed commits required on `main`** — each dev must configure SSH signing and add their key to GitHub as a Signing Key (not an auth key).
