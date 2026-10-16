"""Download character builds from genshin-builds.com into data/builds.json."""

import html
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://genshin-builds.com/en"
OUT = Path(__file__).resolve().parents[1] / "data" / "builds.json"
FIELDS = ("id", "name", "role", "recommended", "sets", "stats", "stats_priority", "talent_priority")


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "genshin-planner"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def decode(v):
    # Astro serializes props as [0, value] or [1, [items]]
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
        kind, x = v
        return [decode(i) for i in x] if kind == 1 else decode(x)
    if isinstance(v, dict):
        return {k: decode(x) for k, x in v.items()}
    return v


def parse_builds(page: str) -> list[dict]:
    for tag in re.findall(r"<astro-island[^>]*>", page):
        if "CharacterBuildTabs" in tag:
            props = json.loads(html.unescape(re.search(r'props="([^"]*)"', tag).group(1)))
            return [{k: b.get(k) for k in FIELDS} for b in decode(props)["builds"]]
    return []


def main():
    slugs = sorted(set(re.findall(r'href="/en/character/([a-z0-9_]+)"', get(f"{BASE}/characters"))))
    result = {}
    for slug in slugs:
        builds = parse_builds(get(f"{BASE}/character/{slug}"))
        if builds:
            result[slug] = builds
        else:
            print(f"no builds: {slug}")
        time.sleep(1)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(result)} characters -> {OUT.name}")


if __name__ == "__main__":
    main()
