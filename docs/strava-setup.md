# Strava Setup

This repository can generate a Strava summary card and display it in the root `README.md`.

## What It Does

The Strava integration:

1. refreshes a Strava access token from a stored refresh token
2. fetches athlete data and stats from the Strava API
3. generates `profile/strava.svg`
4. commits the generated SVG back to the repository

## Files

- `scripts/update_strava.py`: fetches Strava data and renders the SVG
- `.github/workflows/update_strava.yml`: scheduled workflow
- `profile/strava.svg`: generated card
- `svg/strava.svg`: section heading used by the README

## Required GitHub Secrets

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`

## Recommended Extra GitHub Secret

- `GH_REPO_SECRET_TOKEN`

This is a GitHub token used only to update the `STRAVA_REFRESH_TOKEN` repository secret after Strava rotates it.

Why it matters:

- Strava access tokens expire quickly
- Strava refresh tokens can rotate
- when Strava returns a new refresh token, the old one can stop working

Without `GH_REPO_SECRET_TOKEN`, the workflow can work initially but later fail when the stored refresh token becomes stale.

## How To Create `GH_REPO_SECRET_TOKEN`

Create a GitHub fine-grained personal access token with access to this repository and permission to write repository secrets.

Minimum required repository permission:

- `Secrets: Read and write`

Then store it as the repository secret:

- `GH_REPO_SECRET_TOKEN`

## Workflow Behavior

The workflow runs:

- on a daily schedule
- manually from the Actions tab

Workflow order:

1. checkout repository
2. run `scripts/update_strava.py`
3. update `STRAVA_REFRESH_TOKEN` if `GH_REPO_SECRET_TOKEN` is available
4. commit and push `profile/strava.svg` if it changed

## Manual First Run

1. Add the required Strava secrets.
2. Add `GH_REPO_SECRET_TOKEN`.
3. Push the workflow files.
4. Run `Update Strava card` manually from GitHub Actions.
5. Confirm that `profile/strava.svg` was updated in the repository.

## Troubleshooting

### Strava card workflow fails with authentication error

Check:

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`

Also confirm the refresh token was obtained from the same Strava app as the client ID and secret.

### First run works, later runs fail

Most likely cause:

- the refresh token rotated, but the repository secret was not updated

Fix:

- add `GH_REPO_SECRET_TOKEN`
- rerun the workflow
- if needed, generate a new Strava refresh token and replace `STRAVA_REFRESH_TOKEN`

### README shows a placeholder card

That means:

- the Strava workflow has not run successfully yet

Fix:

- run `Update Strava card` manually once
- inspect the Actions log if it fails
