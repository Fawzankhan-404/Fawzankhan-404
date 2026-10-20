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
    if len(days) < 360:
        raise ValueError("Incomplete 365-day contribution calendar; keeping previous artwork")
    counts = {dt.date.fromisoformat(day["date"]): int(day["contributionCount"]) for day in days}
    first = min(counts)
    first -= dt.timedelta(days=(first.weekday() + 1) % 7)
    last = max(counts)
    weeks = (last - first).days // 7 + 1
    split = (weeks + 1) // 2
    active = sum(value > 0 for value in counts.values())
    total = int(calendar["totalContributions"])
    profile_visible = bool(profile_token)
    scope = "PROFILE-VISIBLE CONTRIBUTIONS" if profile_visible else "PUBLIC-ONLY CONTRIBUTIONS"
    note = ("Private counts appear only when enabled in GitHub profile settings"
            if profile_visible else "Public contributions only · private activity is not included")
    p = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="680" height="620" viewBox="0 0 680 620" role="img">
<title>{html.escape(scope.title())} over the last 365 days</title>
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#090c14"/><stop offset=".55" stop-color="#11101a"/><stop offset="1" stop-color="#190b14"/></linearGradient>
<linearGradient id="bar"><stop stop-color="#d62c50"/><stop offset="1" stop-color="#ff7488"/></linearGradient>
<clipPath id="frame"><rect x="1" y="1" width="678" height="618" rx="16"/></clipPath></defs>
<g clip-path="url(#frame)"><rect width="680" height="620" fill="url(#bg)"/>
<path d="M25 133 H655 M25 573 H655" stroke="#49202d"/>
<text x="38" y="48" font-family="Arial,sans-serif" font-size="11" font-weight="700" letter-spacing="3" fill="#f16b84">GITHUB / CONTRIBUTIONS</text>
<text x="38" y="91" font-family="Arial,sans-serif" font-size="28" font-weight="800" fill="#f3e9ee">Activity over time</text>
<text x="40" y="117" font-family="Arial,sans-serif" font-size="12" fill="#bdaab4">Last 365 days · official GitHub contribution calendar</text>
<text x="493" y="74" font-family="Arial,sans-serif" font-size="29" font-weight="800" fill="#ff6c83">{total}</text>
<text x="493" y="96" font-family="Arial,sans-serif" font-size="10" font-weight="700" fill="#c0a9b4">{html.escape(scope)}</text>
<text x="493" y="116" font-family="Arial,sans-serif" font-size="10" fill="#9b8895">{active} active days</text>''']

    # Keep each half of the 53-week calendar at a readable width on narrow screens.
    for panel, (start_week, end_week) in enumerate(((0, split), (split, weeks))):
        top = 190 if panel == 0 else 405
        previous_month = None
        for week in range(start_week, end_week):
            date = first + dt.timedelta(days=week * 7)
            mid = date + dt.timedelta(days=3)
            column = week - start_week
            x = 68 + column * 20.1
            if mid.month != previous_month or column == 0:
                p.append(f'<text x="{x:.1f}" y="{top-13}" font-family="Arial,sans-serif" font-size="10" font-weight="700" fill="#c0a9b4">{mid.strftime("%b").upper()}</text>')
                previous_month = mid.month
            for day in range(7):
                current = date + dt.timedelta(days=day)
                if current > last:
                    continue
                value = counts.get(current, 0)
                xday = x
                y = top + day * 21
                if value == 0:
                    p.append(f'<rect x="{xday:.1f}" y="{y}" width="14" height="14" rx="3" fill="#231724" stroke="#492b3d" stroke-width=".7"/>')
                else:
                    level = 1 if value == 1 else 2 if value < 4 else 3 if value < 8 else 4
                    palette = ("#231724", "#8f2945", "#b72f50", "#e04365", "#ff6981")
                    p.append(f'<rect x="{xday:.1f}" y="{y}" width="14" height="14" rx="3" fill="{palette[level]}"/>')
        if panel == 0:
            for day, letter in enumerate(("S", "M", "T", "W", "T", "F", "S")):
                p.append(f'<text x="43" y="{top + day*21 + 11}" font-family="Arial,sans-serif" font-size="9" fill="#9b8895">{letter}</text>')

    p.append(f'''<text x="38" y="600" font-family="Arial,sans-serif" font-size="10" fill="#bdaab4">{html.escape(note)} · hourly refresh</text>
<rect x="1" y="1" width="678" height="618" rx="16" fill="none" stroke="#713044"/></g></svg>''')
    svg = "".join(p)
    import xml.etree.ElementTree as ET
    ET.fromstring(svg)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    svg_changed = not TARGET.exists() or TARGET.read_text(encoding="utf-8") != svg
    if svg_changed:
        TARGET.write_text(svg, encoding="utf-8")

    # GitHub's image proxy caches README images by URL. Change the URL only when
    # the generated chart changes, so the refreshed content is fetched promptly.
    version = hashlib.sha256(svg.encode("utf-8")).hexdigest()[:12]
    readme = README.read_text(encoding="utf-8")
    image_pattern = re.compile(r'(<img src="\./profile-3d-contrib/profile-night-rainbow\.svg)(?:\?v=[0-9a-f]+)?(")')
    readme_updated, replacements = image_pattern.subn(rf'\1?v={version}\2', readme)
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
