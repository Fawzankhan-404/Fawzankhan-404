#!/usr/bin/env python3
"""Build a responsive contribution calendar from GitHub's official GraphQL API."""
import datetime as dt
import hashlib
import html
import json
import re
import os
from pathlib import Path
from urllib.request import Request, urlopen

USER = "Fawzankhan-404"
TARGET = Path("profile-3d-contrib/profile-night-rainbow.svg")
VERSIONED_PREFIX = "profile-night-rainbow-"
README = Path("README.md")
QUERY = """query($name:String!, $from:DateTime!, $to:DateTime!) {
  viewer { login }
  user(login:$name) { contributionsCollection(from:$from, to:$to) {
    restrictedContributionsCount
    hasAnyRestrictedContributions
    contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
  }}
}"""


def github_request(token, payload, method="POST"):
    request = Request(
        "https://api.github.com/graphql" if method == "POST" else "https://api.github.com/user",
        method=method,
        data=json.dumps(payload).encode() if method == "POST" else None,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": "Profile-Contributions",
                 "Accept": "application/vnd.github+json"},
    )
    with urlopen(request, timeout=40) as response:
        return json.load(response)


def main():
    profile_token = os.environ.get("PROFILE_READ_USER_TOKEN")
    token = profile_token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Missing GitHub token; refusing to generate fabricated activity")
    if profile_token:
        identity = github_request(profile_token, None, method="GET")
        if identity.get("login", "").casefold() != USER.casefold():
            raise RuntimeError("PROFILE_READ_USER_TOKEN must belong to the profile owner")

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start_at = now - dt.timedelta(days=365)
    payload = github_request(token, {
        "query": QUERY,
        "variables": {"name": USER, "from": start_at.isoformat(), "to": now.isoformat()},
    })
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise RuntimeError("GitHub GraphQL returned an error; keeping previous artwork")
    data = payload["data"]
    if profile_token and data.get("viewer", {}).get("login", "").casefold() != USER.casefold():
        raise RuntimeError("Profile token identity did not match the contribution calendar owner")
    collection = data["user"]["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    parsed_days = [(dt.date.fromisoformat(day["date"]), int(day["contributionCount"]))
                   for day in days]
    counts = dict(parsed_days)
    if len(counts) != len(parsed_days):
        raise ValueError("Duplicate dates in GitHub contribution calendar; keeping previous artwork")
    if not counts or len(counts) < 360:
        raise ValueError("Incomplete 365-day contribution calendar; keeping previous artwork")
    if any(value < 0 for value in counts.values()):
        raise ValueError("Negative contribution count returned by GitHub; keeping previous artwork")
    total = int(calendar["totalContributions"])
    if sum(counts.values()) != total:
        raise ValueError("Daily contributions do not match GitHub's calendar total; keeping previous artwork")
    first = min(counts)
    first -= dt.timedelta(days=(first.weekday() + 1) % 7)
    last = max(counts)
    weeks = (last - first).days // 7 + 1
    split = (weeks + 1) // 2
    active = sum(value > 0 for value in counts.values())
    profile_visible = bool(profile_token and collection["hasAnyRestrictedContributions"])
    scope = "PROFILE-VISIBLE CONTRIBUTIONS" if profile_visible else "PUBLIC-ONLY CONTRIBUTIONS"
    note = ("Includes shared private counts · details remain private"
            if profile_visible else "Public-only data · private counts are not included")
    months = {}
    for day, value in counts.items():
        month = day.replace(day=1)
        record = months.setdefault(month, {"total": 0, "active": 0})
        record["total"] += value
        record["active"] += value > 0
    month_keys = sorted(months)
    month_weeks = {}
    for week in range(weeks):
        week_start = first + dt.timedelta(days=week * 7)
        for offset in range(7):
            current = week_start + dt.timedelta(days=offset)
            if current in counts:
                month_weeks.setdefault(current.replace(day=1), week)

    p = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="510" viewBox="0 0 680 510" role="img">
<title>{html.escape(scope.title())} over the last 365 days</title>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#090c14"/><stop offset=".55" stop-color="#11101a"/><stop offset="1" stop-color="#190b14"/></linearGradient>
<linearGradient id="bar"><stop stop-color="#d62c50"/><stop offset="1" stop-color="#ff7488"/></linearGradient>
<clipPath id="frame"><rect x="1" y="1" width="678" height="508" rx="16"/></clipPath></defs>
<g clip-path="url(#frame)"><rect width="680" height="510" fill="url(#bg)"/>
<path d="M25 133 H655 M25 462 H655" stroke="#49202d"/>
<text x="38" y="48" font-family="Arial,sans-serif" font-size="11" font-weight="700" letter-spacing="3" fill="#f16b84">GITHUB / CONTRIBUTIONS</text>
<text x="38" y="91" font-family="Arial,sans-serif" font-size="28" font-weight="800" fill="#f3e9ee">Activity over time</text>
<text x="40" y="117" font-family="Arial,sans-serif" font-size="12" fill="#bdaab4">Daily calendar and monthly contribution totals · last year</text>
<text x="493" y="74" font-family="Arial,sans-serif" font-size="29" font-weight="800" fill="#ff6c83">{total}</text>
<text x="493" y="96" font-family="Arial,sans-serif" font-size="10" font-weight="700" fill="#c0a9b4">{html.escape(scope)}</text>
<text x="493" y="116" font-family="Arial,sans-serif" font-size="10" fill="#9b8895">{active} active days</text>''']

    # Monthly bars make the year trend readable at a glance; the compact
    # weekday heatmap below preserves exact daily detail without dominating.
    p.append('<text x="38" y="155" font-family="Arial,sans-serif" font-size="10" font-weight="700" letter-spacing="1.5" fill="#c0a9b4">MONTHLY ACTIVITY</text>')
    chart_x, chart_step, bar_width, baseline = 48, 48, 24, 268
    max_month = max((months[key]["total"] for key in month_keys), default=1) or 1
    p.append(f'<path d="M54 {baseline} H652" stroke="#513047" stroke-width="1"/>')
    for index, month in enumerate(month_keys):
        x = chart_x + index * chart_step
        values = months[month]
        bar_height = max(3, round(values["total"] / max_month * 82))
        y = baseline - bar_height
        title = f'{month.strftime("%B %Y")}: {values["total"]} contributions, {values["active"]} active days'
        p.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" rx="4" fill="url(#bar)"><title>{html.escape(title)}</title></rect>')
        p.append(f'<text x="{x + bar_width/2:.1f}" y="{y-5}" text-anchor="middle" font-family="Arial,sans-serif" font-size="8" fill="#d8c5ce">{values["total"]}</text>')
        p.append(f'<text x="{x + bar_width/2:.1f}" y="288" text-anchor="middle" font-family="Arial,sans-serif" font-size="8" font-weight="700" fill="#bdaab4">{month.strftime("%b %y").upper()}</text>')

    p.append('<text x="38" y="323" font-family="Arial,sans-serif" font-size="10" font-weight="700" letter-spacing="1.5" fill="#c0a9b4">DAILY CALENDAR</text>')
    for day, label in enumerate(("S", "M", "T", "W", "T", "F", "S")):
        p.append(f'<text x="43" y="{367 + day*11 + 7}" font-family="Arial,sans-serif" font-size="8" font-weight="700" fill="#9b8895">{label}</text>')
    for month, week in month_weeks.items():
        x = 70 + week * 11.2
        p.append(f'<text x="{x:.1f}" y="348" font-family="Arial,sans-serif" font-size="8" font-weight="700" fill="#bdaab4">{month.strftime("%b").upper()}</text>')
    for week in range(weeks):
        week_start = first + dt.timedelta(days=week * 7)
        for day in range(7):
            current = week_start + dt.timedelta(days=day)
            if current not in counts:
                continue
            value = counts[current]
            x, y = 70 + week * 11.2, 367 + day * 11
            if value == 0:
                p.append(f'<rect x="{x:.1f}" y="{y}" width="8" height="8" rx="2" fill="#241a25" stroke="#513047" stroke-width=".55"><title>{current.isoformat()}: no contributions</title></rect>')
            else:
                level = 1 if value == 1 else 2 if value < 4 else 3 if value < 8 else 4
                palette = ("#231724", "#8f2945", "#b72f50", "#e04365", "#ff6981")
                p.append(f'<rect x="{x:.1f}" y="{y}" width="8" height="8" rx="2" fill="{palette[level]}"><title>{current.isoformat()}: {value} contributions</title></rect>')

    p.append(f'''<text x="38" y="464" font-family="Arial,sans-serif" font-size="9" fill="#bdaab4">Less</text>
<rect x="68" y="456" width="9" height="9" rx="2" fill="#241a25" stroke="#513047" stroke-width=".55"/><rect x="84" y="456" width="9" height="9" rx="2" fill="#8f2945"/><rect x="100" y="456" width="9" height="9" rx="2" fill="#b72f50"/><rect x="116" y="456" width="9" height="9" rx="2" fill="#e04365"/><rect x="132" y="456" width="9" height="9" rx="2" fill="#ff6981"/>
<text x="148" y="464" font-family="Arial,sans-serif" font-size="9" fill="#bdaab4">More daily activity · monthly totals are labeled above</text>
<text x="38" y="492" font-family="Arial,sans-serif" font-size="9" fill="#9b8895">{html.escape(note)} · updated hourly</text>
<rect x="1" y="1" width="678" height="508" rx="16" fill="none" stroke="#713044"/></g></svg>''')
    svg = "".join(p)
    import xml.etree.ElementTree as ET
    ET.fromstring(svg)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    svg_changed = not TARGET.exists() or TARGET.read_text(encoding="utf-8") != svg
    if svg_changed:
        TARGET.write_text(svg, encoding="utf-8")

    # GitHub's README image proxy kept serving stale bytes despite a changed
    # query string. Use a content-versioned filename as the cache key, and keep
    # only the current version in the repository.
    version = hashlib.sha256(svg.encode("utf-8")).hexdigest()[:12]
    versioned_target = TARGET.with_name(f"{VERSIONED_PREFIX}{version}.svg")
    if not versioned_target.exists() or versioned_target.read_text(encoding="utf-8") != svg:
        versioned_target.write_text(svg, encoding="utf-8")
    for stale in TARGET.parent.glob(f"{VERSIONED_PREFIX}*.svg"):
        if stale != versioned_target:
            stale.unlink()
    readme = README.read_text(encoding="utf-8")
    image_pattern = re.compile(
        r'(<img src="\./profile-3d-contrib/)'
        r'(?:profile-night-rainbow(?:-[0-9a-f]{12})?\.svg(?:\?v=[0-9a-f]+)?)'
        r'(")'
    )
    readme_updated, replacements = image_pattern.subn(
        rf'\1{versioned_target.name}\2', readme
    )
    if replacements != 1:
        raise RuntimeError("Expected exactly one contribution image reference in README")
    readme_changed = readme_updated != readme
    if readme_changed:
        README.write_text(readme_updated, encoding="utf-8")

    if svg_changed or readme_changed:
        mode = "profile-visible" if profile_visible else "public-only"
        print(f"Updated contribution artwork: {total} {mode} contributions across 365 days, {active} active days")
    else:
        print("Contribution data unchanged; no files need updating")


if __name__ == "__main__":
    main()
