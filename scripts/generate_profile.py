#!/usr/bin/env python3
"""Fetch public GitHub data and render a deterministic terminal profile GIF."""
import argparse
from functools import lru_cache
import io
import subprocess
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
W, H = 960, 480
BG, PANEL, LINE = "#0b1220", "#111d2e", "#24364b"
TEXT, MUTED, ACCENT = "#e4edf7", "#a0b2c8", "#5eead4"
FONT_DIR = Path(os.environ.get("PROFILE_FONT_DIR", "/usr/share/fonts/truetype/dejavu"))


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-animation",
               "X-GitHub-Api-Version": "2022-11-28"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_data(config):
    owner = urllib.parse.quote(config["username"], safe="")
    scope = config.get("repository_scope", "owned_public")
    if scope not in {"owned_public", "all_accessible"}:
        raise ValueError("repository_scope must be 'owned_public' or 'all_accessible'")
    if scope == "all_accessible" and not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GH_TOKEN is required when repository_scope is 'all_accessible'")

    repos = []
    page = 1
    while True:
        if scope == "all_accessible":
            path = "/user/repos?visibility=all&affiliation=owner,collaborator,organization_member"
        else:
            path = f"/users/{owner}/repos?type=owner"
        batch = api(f"{path}&per_page=100&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    excluded = set(config["exclude_repositories"])
    repos = [r for r in repos if not r["fork"] and not r.get("archived")
             and (scope == "all_accessible" or not r.get("private"))
             and r["name"] not in excluded and r.get("full_name") not in excluded]
    languages = Counter()
    for repo in sorted(repos, key=lambda r: r["name"]):
        repo_owner = urllib.parse.quote(repo.get("owner", {}).get("login", config["username"]), safe="")
        name = urllib.parse.quote(repo["name"], safe="")
        languages.update(api(f"/repos/{repo_owner}/{name}/languages"))
    return {"languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
            "repository_count": len(repos)}


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ("DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf")), size)


def fit(draw, value, size, width):
    value = " ".join(value.split())
    if draw.textlength(value, font=font(size)) <= width:
        return value
    while value and draw.textlength(value + "…", font=font(size)) > width:
        value = value[:-1]
    return value + "…"


@lru_cache(maxsize=8)
def logo_image(path):
    try:
        result = subprocess.run(
            ["/usr/bin/python3", str(ROOT / "scripts/rasterize_logo.py"), str(ROOT / path)],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Could not render logo {path}:\n{details}") from exc
    logo = Image.open(io.BytesIO(result.stdout)).convert("RGBA")
    bounds = logo.getbbox()
    if not bounds:
        raise ValueError(f"Logo is empty: {path}")
    logo = logo.crop(bounds)
    logo.thumbnail((290, 100), Image.Resampling.LANCZOS)
    return logo


def frame(config, data, scene, progress):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    def text(x, y, value, size=20, color=TEXT, bold=False):
        d.text((x, y), value, font=font(size, bold), fill=color)
    d.rounded_rectangle((12, 12, W-13, H-13), radius=18, outline=LINE, width=2)
    for i, color in enumerate(("#fb7185", "#fbbf24", ACCENT)):
        d.ellipse((32+i*23, 32, 43+i*23, 43), fill=color)
    text(120, 27, f'{config["username"]} / workspace', 17, MUTED)
    text(780, 27, "PROFILE OS", 16, ACCENT)
    d.line((28, 64, 932, 64), fill=LINE)
    labels = ["whoami", "work --current", "academic --degrees", "toolbox --list", "github --languages", "learn --next"]
    command = "$ " + labels[scene]
    text(44, 84, command[:max(1, int(progress*len(command)*3))], 22, ACCENT)
    if scene == 0:
        text(44, 150, config["name"], 48, TEXT, True)
        text(46, 221, config["tagline"], 24, MUTED)
        text(46, 298, "build  >  test  >  improve", 22, ACCENT)
        points = [(615, 326), (680, 256), (757, 287), (833, 191), (895, 220)]
        d.line(points, fill=LINE, width=3)
        count = min(4, int(progress*5))
        if count:
            d.line(points[:count+1], fill=ACCENT, width=4)
        for x,y in points:
            d.ellipse((x-6,y-6,x+6,y+6), fill=BG, outline=ACCENT, width=2)
        x,y = points[count]
        d.rounded_rectangle((x-11,y-11,x+11,y+11), radius=5, fill=ACCENT)
    elif scene == 1:
        text(44, 137, "Current work", 29, TEXT, True)
        for i, work in enumerate(config.get("work", [])[:2]):
            x, y = 44 + i * 446, 194
            d.rounded_rectangle((x, y, x+426, y+205), radius=12, fill=PANEL, outline=LINE)
            logo = logo_image(work["logo"])
            im.paste(logo, (x+24, y+20+(100-logo.height)//2), logo)
            text(x+24, y+135, work["company"], 21, MUTED)
            text(x+24, y+170, fit(d, work["role"], 23, 380), 23, ACCENT)
    elif scene == 2:
        text(44, 137, "Academic", 29, TEXT, True)
        for i, study in enumerate(config.get("academic", [])[:2]):
            x, y = 44 + i * 446, 190
            d.rounded_rectangle((x, y, x+426, y+220), radius=12, fill=PANEL, outline=LINE)
            d.rounded_rectangle((x+16, y+12, x+410, y+122), radius=8, fill="#f1f5f9")
            logo = logo_image(study["logo"])
            im.paste(logo, (x+(426-logo.width)//2, y+17+(100-logo.height)//2), logo)
            text(x+24, y+137, study["degree"] + " in", 23, MUTED)
            text(x+24, y+174, fit(d, study["field"], 25, 380), 25, ACCENT)
    elif scene == 3:
        text(44, 137, "Tools I work with", 27, TEXT, True)
        for i, skill in enumerate(config["skills"][:9]):
            x, y = 44+(i%3)*293, 194+(i//3)*65
            d.rounded_rectangle((x,y,x+275,y+49), radius=9, fill=PANEL, outline=LINE)
            active = progress >= i/12
            text(x+15,y+11, ("> " if active else "  ")+skill, 21, ACCENT if active else MUTED)
    elif scene == 4:
        text(44, 132, "Languages across my repositories", 25, TEXT, True)
        total = sum(data["languages"].values())
        for i,(name,count) in enumerate(list(data["languages"].items())[:5]):
            y = 186+i*40
            text(44,y,fit(d,name,19,190),19)
            d.rounded_rectangle((250,y+4,780,y+22), radius=5, fill=PANEL)
            width = round(530*count/total*min(1,progress*2)) if total else 0
            if width > 1:
                d.rounded_rectangle((250,y+4,250+width,y+22), radius=5, fill=ACCENT)
            text(803,y,f"{count/total:.1%}",19,ACCENT)
        if not total:
            text(44,210,"No language data available yet.",22,MUTED)
        text(44,394,f'{data["repository_count"]} public originals / bytes of code / excludes profile',16,MUTED)
    else:
        text(44,145,"Always learning.",36,TEXT,True)
        for i, value in enumerate(config["learning"][:3]):
            text(46,216+i*44, "+ " + value,26,ACCENT)
        text(46,365,"github.com/"+config["username"],23,MUTED)
    d.line((28,433,932,433),fill=LINE)
    text(44,448,"AI / PERCEPTION / ROBOTICS",14,MUTED)
    for i in range(6):
        d.rounded_rectangle((773+i*28,450,789+i*28,455),radius=2,fill=ACCENT if scene==i else LINE)
    return im


def render(config, data, directory):
    frames, durations = [], []
    for scene in range(6):
        for step in range(10):
            frames.append(frame(config,data,scene,step/9).quantize(colors=64))
            durations.append(100 if step < 9 else (3100 if scene in (1,2,4) else 2300))
    frames[0].save(directory / "terminal.gif",save_all=True,append_images=frames[1:],
                   duration=durations,loop=0,optimize=True,disposal=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline",action="store_true",help="Render from the last successful data snapshot")
    args = parser.parse_args()
    config = json.loads((PROFILE/"config.json").read_text())
    data = json.loads((PROFILE/"data.json").read_text()) if args.offline else fetch_data(config)
    # Include renderer and dependency versions so visual changes rebuild as well.
    import PIL
    digest = hashlib.sha256(Path(__file__).read_bytes() + json.dumps([config,data],sort_keys=True).encode()
                            + PIL.__version__.encode())
    for name in ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"):
        digest.update((FONT_DIR/name).read_bytes())
    digest.update((ROOT / "scripts/rasterize_logo.py").read_bytes())
    for entry in config.get("work", []) + config.get("academic", []):
        digest.update((ROOT / entry["logo"]).read_bytes())
    signature = digest.hexdigest()
    if all((PROFILE/name).exists() for name in ("terminal.gif","data.json","render.sha256")) and (PROFILE/"render.sha256").read_text().strip()==signature:
        print("Profile content unchanged; keeping existing animation.")
        return
    # Fetch and render completely before replacing any checked-in assets.
    with tempfile.TemporaryDirectory(dir=PROFILE) as tmp:
        directory = Path(tmp)
        render(config,data,directory)
        (directory/"data.json").write_text(json.dumps(data,indent=2)+"\n")
        (directory/"render.sha256").write_text(signature+"\n")
        for name in ("terminal.gif","data.json","render.sha256"):
            (directory/name).replace(PROFILE/name)
    print("Updated profile animation and public data snapshot.")


if __name__ == "__main__":
    main()
