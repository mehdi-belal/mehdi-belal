# Profile animation

`README.md` is the profile page for `mehdi-belal`. The terminal GIF is generated
with Python and Pillow; no image-generation service is used.

## Edit the content

Edit `profile/config.json` for the name, tagline, skills, learning interests,
current roles, academic background, and repositories excluded from statistics.
The README shows the animation first, followed by contact buttons and workflow
badges. Edit contact destinations in `README.md`; button artwork lives in `assets/`.

The GitHub API supplies language byte totals. Pagination
includes all public owned repositories; forks, archived repositories, and the
profile itself are excluded. The five largest languages are shown as shares of
all included language bytes, so their percentages may total less than 100%.
No private repository data or tokens are written to the snapshot.

## Automatic updates

`.github/workflows/update_profile.yml` runs Mondays at 02:00 UTC, manually, and
when renderer/configuration files change on main or master. It installs Pillow
and DejaVu fonts, runs tests, fetches data using the built-in `GITHUB_TOKEN`, and
commits changed output. No personal token is needed. Repository rules must allow
the workflow to push to the default branch.

The output is `profile/terminal.gif`, a 960 × 480, approximately 22-second loop,
plus a public data snapshot and a rendering fingerprint. Unchanged
content is skipped. Fetch/render failures happen before outputs are replaced, so
the previous GIF remains usable. Renderer, Pillow, and font changes also invalidate
the fingerprint.

## Run locally

Requires Python 3.10+ and the DejaVu Sans Mono regular/bold fonts. On Ubuntu:

```bash
sudo apt-get install fonts-dejavu-core python3-gi python3-gi-cairo python3-cairo gir1.2-rsvg-2
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/generate_profile.py
```

Set `GH_TOKEN` for a higher GitHub API rate limit. Set `PROFILE_FONT_DIR` if fonts
are installed somewhere other than `/usr/share/fonts/truetype/dejavu`.
Use `--offline` to regenerate from `profile/data.json` without network access.

## Codeberg mirror

The existing sync workflow uses the `CODEBERG_TOKEN` repository secret. It runs
on pushes, manually, and after a successful profile-animation workflow on the
default branch. This completion trigger is needed because commits made with
`GITHUB_TOKEN` do not trigger another push workflow.

## Removed integration

The former fitness integration and SVG card workflows have been removed.
Their old repository secrets are no longer used; repository administrators can
remove those credentials from GitHub settings.

## Current work scene

Edit `work` in `profile/config.json` to change the two roles or logo paths. The
original SVG logos in `assets/` are rasterized with system Python and librsvg;
colours and aspect ratios are preserved. Logo changes trigger the workflow and
invalidate the rendering fingerprint.

## Academic scene

Edit `academic` in `profile/config.json` for degrees, fields, institutions, and
logo paths. Up to two entries are shown after Current work. University logos
retain their original colours on light panels. Changes to these SVG assets
trigger regeneration and invalidate the rendering fingerprint.
