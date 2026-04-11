#!/usr/bin/env python3
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def request_json(url: str, method: str = "GET", data: dict | None = None, headers: dict | None = None) -> dict | list:
    encoded = None
    merged_headers = {"Accept": "application/json"}
    if headers:
        merged_headers.update(headers)

    if data is not None:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        merged_headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(url, data=encoded, headers=merged_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {details}") from exc


def is_missing_activity_read(exc: RuntimeError) -> bool:
    message = str(exc)
    return (
        "https://www.strava.com/api/v3/athlete/activities" in message
        and "activity:read_permission" in message
        and "missing" in message
    )


def fmt_distance(meters: float) -> str:
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{meters:.0f} m"


def fmt_elevation(meters: float) -> str:
    return f"{meters:.0f} m"


def fmt_activity_date(value: str) -> str:
    if not value:
        return "Unknown date"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%b %d, %Y")


def stat_block(title: str, totals: dict) -> tuple[str, str, str]:
    count = int(totals.get("count", 0))
    distance = fmt_distance(float(totals.get("distance", 0)))
    elevation = fmt_elevation(float(totals.get("elevation_gain", 0)))
    return title, f"{count} activities", f"{distance} • {elevation}"


def longest_ride_block(activities: list[dict]) -> tuple[str, str, str]:
    rides = [
        activity
        for activity in activities
        if str(activity.get("type", "")).lower() == "ride"
    ]
    if not rides:
        return "Longest ride", "Unavailable", "Requires public ride activity data"

    longest = max(rides, key=lambda activity: float(activity.get("distance", 0)))
    name = str(longest.get("name", "Untitled ride")).strip() or "Untitled ride"
    distance = fmt_distance(float(longest.get("distance", 0)))
    date = fmt_activity_date(longest.get("start_date_local") or longest.get("start_date") or "")
    return "Longest ride", html.escape(name), f"{distance} • {date}"


def write_github_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def build_svg(athlete: dict, stats: dict, activities: list[dict], activities_unavailable_reason: str = "") -> str:
    athlete_name = html.escape(f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip() or "Strava Athlete")
    location_parts = [athlete.get("city", ""), athlete.get("state", ""), athlete.get("country", "")]
    location = html.escape(", ".join(part for part in location_parts if part))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    ride_block = stat_block("Ride YTD", stats.get("ytd_ride_totals", {}))
    longest_block = longest_ride_block(activities)
    activity_note = activities_unavailable_reason or "Longest ride is derived from recent public ride activities."

    block_x = 44
    blocks_svg = []
    for title, line_one, line_two in [ride_block, longest_block]:
        blocks_svg.append(
            f"""
  <rect x="{block_x}" y="92" width="300" height="110" rx="16" fill="#F8FAFC" stroke="#E2E8F0"/>
  <text x="{block_x + 20}" y="118" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="20">{html.escape(title)}</text>
  <text x="{block_x + 20}" y="146" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="24" font-weight="600">{html.escape(line_one)}</text>
  <text x="{block_x + 20}" y="172" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="16">{html.escape(line_two)}</text>"""
        )
        block_x += 316

    location_svg = ""
    if location:
        location_svg = f'<text x="44" y="62" fill="#64748B" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="18">{location}</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="340" viewBox="0 0 720 340" role="img" aria-labelledby="title desc">
  <title id="title">Strava activity summary</title>
  <desc id="desc">Generated summary card for Strava ride totals and longest ride.</desc>
  <rect width="720" height="340" rx="24" fill="#ffffff"/>
  <rect x="1" y="1" width="718" height="338" rx="23" fill="none" stroke="#E2E8F0"/>
  <text x="44" y="42" fill="#FC4C02" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="28" font-weight="700">STRAVA</text>
  <text x="162" y="42" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="28">{athlete_name}</text>
  {location_svg}
  {''.join(blocks_svg)}
  <text x="44" y="250" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="18">{html.escape(activity_note)}</text>
  <text x="676" y="318" text-anchor="end" fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="14">Updated {generated_at}</text>
</svg>
"""


def main() -> int:
    client_id = env("STRAVA_CLIENT_ID")
    client_secret = env("STRAVA_CLIENT_SECRET")
    refresh_token = env("STRAVA_REFRESH_TOKEN")

    token_response = request_json(
        "https://www.strava.com/oauth/token",
        method="POST",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    access_token = token_response["access_token"]
    new_refresh_token = token_response["refresh_token"]

    headers = {"Authorization": f"Bearer {access_token}"}
    athlete = request_json("https://www.strava.com/api/v3/athlete", headers=headers)
    athlete_id = athlete["id"]
    stats = request_json(f"https://www.strava.com/api/v3/athletes/{athlete_id}/stats", headers=headers)
    activities: list[dict] = []
    activities_unavailable_reason = ""
    try:
        fetched_activities = request_json(
            "https://www.strava.com/api/v3/athlete/activities?per_page=3&page=1",
            headers=headers,
        )
        if isinstance(fetched_activities, list):
            activities = fetched_activities
    except RuntimeError as exc:
        if is_missing_activity_read(exc):
            activities_unavailable_reason = "Recent activities unavailable: token is missing activity:read scope."
        else:
            raise

    svg = build_svg(athlete, stats, activities, activities_unavailable_reason)
    os.makedirs("profile", exist_ok=True)
    with open("profile/strava.svg", "w", encoding="utf-8") as handle:
        handle.write(svg)

    write_github_output("refresh_token", new_refresh_token)
    write_github_output("athlete_id", str(athlete_id))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
