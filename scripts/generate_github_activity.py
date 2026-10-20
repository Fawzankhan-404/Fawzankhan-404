#!/usr/bin/env python3
"""Build a readable profile contribution SVG using the official GitHub GraphQL API."""
import datetime as dt
import html
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

USER = "Fawzankhan-404"
TARGET = Path("profile-3d-contrib/profile-night-rainbow.svg")
QUERY = """query($name:String!) {
  user(login:$name) { contributionsCollection {
    contributionCalendar {totalContributions weeks {contributionDays {date contributionCount}}}
  }}
}"""

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN; refusing to generate made-up activity")
    request = Request("https://api.github.com/graphql", method="POST",
       data=json.dumps({"query":QUERY,"variables":{"name":USER}}).encode(),
       headers={"Authorization":"Bearer "+token,"Content-Type":"application/json",
                "User-Agent":"Profile-Contributions","Accept":"application/vnd.github+json"})
    with urlopen(request,timeout=40) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data",{}).get("user"):
        raise RuntimeError("GitHub GraphQL error: "+str(payload.get("errors",payload)))
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    ds = [day for week in cal["weeks"] for day in week["contributionDays"]]
    if len(ds)<300:
        raise ValueError("Incomplete contribution calendar; keeping previous artwork")
    count = {dt.date.fromisoformat(d["date"]):int(d["contributionCount"]) for d in ds}
    start = min(count)
    start -= dt.timedelta(days=(start.weekday()+1)%7)
    end = max(count)
    total = int(cal["totalContributions"])
    active = sum(v>0 for v in count.values())
    weeks = (end-start).days//7+1
    p=['''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="480" viewBox="0 0 1200 480"><title>GitHub contribution activity</title>
    <defs><linearGradient id="bg"><stop stop-color="#090c14"/><stop offset=".6" stop-color="#11101a"/><stop offset="1" stop-color="#140912"/></linearGradient>
    <linearGradient id="beam"><stop stop-color="#d62c50" stop-opacity="0"/><stop offset=".5" stop-color="#ff7488" stop-opacity=".85"/><stop offset="1" stop-color="#d62c50" stop-opacity="0"/></linearGradient>
    <clipPath id="frame"><rect x="1" y="1" width="1198" height="478" rx="16"/></clipPath></defs>
    <g clip-path="url(#frame)"><rect width="1200" height="480" fill="url(#bg)"/>
    <path d="M25 130 H1175 M25 424 H1175" stroke="#49202d"/>
    <text x="42" y="51" font-family="Arial" font-size="12" font-weight="700" letter-spacing="4" fill="#f16b84">GITHUB / CONTRIBUTIONS</text>
    <text x="40" y="97" font-family="Arial" font-size="33" font-weight="800" fill="#f3e9ee">Activity over time</text>
    <text x="44" y="119" font-family="Arial" font-size="12" fill="#a7929e">Last 12 months of GitHub contributions</text>''']
    p.extend([f'<text x="767" y="69" font-family="Arial" font-size="33" font-weight="800" fill="#ff6c83">{total}</text>',
        '<text x="767" y="93" font-family="Arial" font-size="11" fill="#ae9ba8">YEARLY CONTRIBUTIONS</text>',
        f'<text x="1015" y="69" font-family="Arial" font-size="33" font-weight="800" fill="#ff6c83">{active}</text>',
        '<text x="1015" y="93" font-family="Arial" font-size="11" fill="#ae9ba8">ACTIVE DAYS</text>'])
    previous = None
    for week in range(weeks):
        mid = start+dt.timedelta(days=week*7+3)
        if mid.month != previous:
            p.append(f'<text x="{69+week*19.65:.1f}" y="173" fill="#bfaeb6" font-family="Arial" font-size="12">{mid.strftime("%b").upper()}</text>')
            previous=mid.month
    for char,row in (("S",0),("T",2),("T",4),("S",6)):
        p.append(f'<text x="43" y="{207+row*27+7}" fill="#8d7886" font-family="Arial" font-size="11">{char}</text>')
    palette=("#231724","#8f2945","#b72f50","#e04365","#ff6981")
    for week in range(weeks):
        for day in range(7):
            date=start+dt.timedelta(days=7*week+day)
            if date>end: continue
            n=count.get(date,0)
            tier=0 if n==0 else 1 if n==1 else 2 if n<4 else 3 if n<8 else 4
            x,y=69+week*19.65,207+day*27
            if not tier:
                p.append(f'<rect x="{x:.1f}" y="{y}" width="14.4" height="14.4" rx="2.7" fill="#231724" stroke="#3d2736" stroke-width=".6"/>')
            else:
                h=3.4+tier*2.1
                yt=y+14.4-h
                color=palette[tier]
                p.append(f'<rect x="{x:.1f}" y="{yt:.1f}" width="14.4" height="{h:.1f}" fill="{color}" opacity=".72"/>')
                p.append(f'<path d="M{x+14.4:.1f} {yt:.1f} l3 -2.8 v{h:.1f} l-3 2.8Z" fill="#65172e"/>')
                p.append(f'<path d="M{x:.1f} {yt:.1f} l3 -2.8 h14.4 l-3 2.8Z" fill="{color}" stroke="#ffa1ae" stroke-opacity=".28" stroke-width=".55"/>')
    p.append('<text x="45" y="451" font-family="Arial" font-size="11" fill="#9b8895">OFFICIAL GITHUB DATA · AUTOMATIC HOURLY REFRESH</text>')
    p.append('<text x="928" y="451" font-family="Arial" font-size="11" fill="#9b8895">LESS</text>')
    for i,color in enumerate(palette):
        p.append(f'<rect x="{967+i*17}" y="439" width="13" height="13" rx="2" fill="{color}"/>')
    p.append('''<text x="1055" y="451" font-family="Arial" font-size="11" fill="#9b8895">MORE</text>
    <rect x="-1200" y="477" width="1200" height="3" fill="url(#beam)"><animate attributeName="x" values="-1200;1200" dur="2.8s" repeatCount="indefinite"/></rect></g>
    <rect x="1" y="1" width="1198" height="478" rx="16" fill="none" stroke="#713044"/></svg>''')
    import xml.etree.ElementTree as ET
    svg=''.join(p)
    ET.fromstring(svg)
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    # Do not rewrite when contributions have not changed.
    if TARGET.exists() and TARGET.read_text(encoding="utf-8")==svg:
        print("Contribution data unchanged")
    else:
        TARGET.write_text(svg,encoding="utf-8")
        print(f"Updated {TARGET}: {total} contributions, {active} active days")

if __name__=="__main__":
    main()
