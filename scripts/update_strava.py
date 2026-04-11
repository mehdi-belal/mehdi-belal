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


def fetch_activities_page(headers: dict[str, str], page: int, per_page: int = 100) -> list[dict]:
    batch = request_json(
        f"https://www.strava.com/api/v3/athlete/activities?per_page={per_page}&page={page}",
        headers=headers,
    )
    if isinstance(batch, list):
        return batch
    return []


def fetch_latest_ride(headers: dict[str, str], max_pages: int = 5) -> dict | None:
    for page in range(1, max_pages + 1):
        batch = fetch_activities_page(headers, page)
        if not batch:
            return None
        for activity in batch:
            if "ride" in str(activity.get("type", "")).lower():
                return activity
    return None


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


def rides_total_block(totals: dict) -> tuple[str, str, str]:
    count = int(totals.get("count", 0))
    elevation = fmt_elevation(float(totals.get("elevation_gain", 0)))
    return "Total rides", str(count), f"All-time rides • {elevation} climbed"


def total_km_block(totals: dict) -> tuple[str, str, str]:
    distance = fmt_distance(float(totals.get("distance", 0)))
    return "Total km", distance, "All-time ride distance"


def longest_ride_block(stats: dict) -> tuple[str, str, str]:
    distance = fmt_distance(float(stats.get("biggest_ride_distance", 0)))
    return "Longest ride", distance, "Biggest ride distance reported by Strava"


def latest_ride_block(activity: dict | None, unavailable_reason: str = "") -> tuple[str, str, str]:
    if not activity:
        return "Latest ride", "Unavailable", unavailable_reason or "No accessible ride found"

    name = str(activity.get("name", "Untitled ride")).strip() or "Untitled ride"
    distance = fmt_distance(float(activity.get("distance", 0)))
    date = fmt_activity_date(activity.get("start_date_local") or activity.get("start_date") or "")
    return "Latest ride", html.escape(name), f"{distance} • {date}"


def decode_polyline(polyline: str) -> list[tuple[float, float]]:
    index = 0
    lat = 0
    lng = 0
    coordinates: list[tuple[float, float]] = []

    while index < len(polyline):
        shift = 0
        result = 0
        while True:
            byte = ord(polyline[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else result >> 1
        lat += delta_lat

        shift = 0
        result = 0
        while True:
            byte = ord(polyline[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lng = ~(result >> 1) if result & 1 else result >> 1
        lng += delta_lng

        coordinates.append((lat / 1e5, lng / 1e5))

    return coordinates


def render_map_path(activity: dict | None, x: int, y: int, width: int, height: int) -> str:
    if not activity:
        return (
            f'<text x="{x + width / 2:.0f}" y="{y + height / 2:.0f}" text-anchor="middle" '
            'fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" '
            'font-size="16">No latest ride map available</text>'
        )

    polyline = (
        activity.get("map", {}).get("summary_polyline", "")
        if isinstance(activity.get("map", {}), dict)
        else ""
    )
    if not polyline:
        return (
            f'<text x="{x + width / 2:.0f}" y="{y + height / 2:.0f}" text-anchor="middle" '
            'fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" '
            'font-size="16">Latest ride has no map polyline</text>'
        )

    points = decode_polyline(polyline)
    if len(points) < 2:
        return (
            f'<text x="{x + width / 2:.0f}" y="{y + height / 2:.0f}" text-anchor="middle" '
            'fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" '
            'font-size="16">Latest ride map is too small to render</text>'
        )

    lats = [point[0] for point in points]
    lngs = [point[1] for point in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    lat_span = max(max_lat - min_lat, 1e-9)
    lng_span = max(max_lng - min_lng, 1e-9)
    padding = 12
    usable_width = width - (padding * 2)
    usable_height = height - (padding * 2)
    scale = min(usable_width / lng_span, usable_height / lat_span)
    offset_x = x + padding + (usable_width - (lng_span * scale)) / 2
    offset_y = y + padding + (usable_height - (lat_span * scale)) / 2

    path_parts: list[str] = []
    for idx, (lat_value, lng_value) in enumerate(points):
        px = offset_x + ((lng_value - min_lng) * scale)
        py = offset_y + ((max_lat - lat_value) * scale)
        command = "M" if idx == 0 else "L"
        path_parts.append(f"{command}{px:.2f} {py:.2f}")

    start_lat, start_lng = points[0]
    end_lat, end_lng = points[-1]
    start_x = offset_x + ((start_lng - min_lng) * scale)
    start_y = offset_y + ((max_lat - start_lat) * scale)
    end_x = offset_x + ((end_lng - min_lng) * scale)
    end_y = offset_y + ((max_lat - end_lat) * scale)

    return (
        f'<path d="{" ".join(path_parts)}" fill="none" stroke="#FC4C02" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{start_x:.2f}" cy="{start_y:.2f}" r="4" fill="#0F172A"/>'
        f'<circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="4" fill="#FC4C02"/>'
    )


def write_github_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def build_svg(athlete: dict, stats: dict, latest_ride: dict | None, activities_unavailable_reason: str = "") -> str:
    athlete_name = html.escape(f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip() or "Strava Athlete")
    location_parts = [athlete.get("city", ""), athlete.get("state", ""), athlete.get("country", "")]
    location = html.escape(", ".join(part for part in location_parts if part))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    longest_ride = longest_ride_block(stats)
    all_ride_totals = stats.get("all_ride_totals", {})
    total_rides = rides_total_block(all_ride_totals)
    total_km = total_km_block(all_ride_totals)
    latest_block = latest_ride_block(latest_ride, activities_unavailable_reason)
    blocks_svg = []
    layout = [
        (44, 92, longest_ride),
        (258, 92, total_rides),
        (472, 92, total_km),
    ]
    for x, y, (title, line_one, line_two) in layout:
        blocks_svg.append(
            f"""
  <rect x="{x}" y="{y}" width="204" height="96" rx="16" fill="#F8FAFC" stroke="#E2E8F0"/>
  <text x="{x + 20}" y="{y + 28}" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="20">{html.escape(title)}</text>
  <text x="{x + 20}" y="{y + 56}" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="24" font-weight="600">{html.escape(line_one)}</text>
  <text x="{x + 20}" y="{y + 78}" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="16">{html.escape(line_two)}</text>"""
        )

    latest_title, latest_line_one, latest_line_two = latest_block
    map_svg = render_map_path(latest_ride, 394, 246, 250, 148)
    latest_panel_svg = f"""
  <rect x="44" y="218" width="632" height="176" rx="20" fill="#F8FAFC" stroke="#E2E8F0"/>
  <text x="68" y="250" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="22">{html.escape(latest_title)}</text>
  <text x="68" y="286" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="28" font-weight="600">{html.escape(latest_line_one)}</text>
  <text x="68" y="316" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="18">{html.escape(latest_line_two)}</text>
  <rect x="394" y="246" width="250" height="148" rx="16" fill="#FFFFFF" stroke="#E2E8F0"/>
  {map_svg}
"""

    location_svg = ""
    if location:
        location_svg = f'<text x="44" y="62" fill="#64748B" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="18">{location}</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="430" viewBox="0 0 720 430" role="img" aria-labelledby="title desc">
  <title id="title">Strava activity summary</title>
  <desc id="desc">Generated summary card for Strava ride totals and latest ride map.</desc>
  <rect width="720" height="430" rx="24" fill="#ffffff"/>
  <rect x="1" y="1" width="718" height="428" rx="23" fill="none" stroke="#E2E8F0"/>
  <text x="44" y="42" fill="#FC4C02" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="28" font-weight="700">STRAVA</text>
  <text x="162" y="42" fill="#0F172A" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="28">{athlete_name}</text>
  {location_svg}
  {''.join(blocks_svg)}
  {latest_panel_svg}
  <text x="676" y="406" text-anchor="end" fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="14">Updated {generated_at}</text>
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
    latest_ride: dict | None = None
    activities_unavailable_reason = ""
    try:
        latest_ride = fetch_latest_ride(headers)
    except RuntimeError as exc:
        if is_missing_activity_read(exc):
            activities_unavailable_reason = "Latest ride details unavailable: token is missing activity:read scope."
        else:
            raise

    svg = build_svg(athlete, stats, latest_ride, activities_unavailable_reason)
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
