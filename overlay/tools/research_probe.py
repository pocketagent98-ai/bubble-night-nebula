"""Fetches the three reference store pages and turns them into a feature matrix.

This is the "the notebook researches for itself" step. It is deliberately
defensive: if the sandbox has no route to the store (a locked-down Colab, an
offline runner), it falls back to the snapshot in
`docs/reference_snapshot.json`, which was captured from the same three pages,
and says so in the output. It never invents a feature it did not read.

Run:  python3 tools/research_probe.py [--out docs]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REFS = [
    ("dragon", "game.bubble.shooter.dragon.pop", "Bubble Shooter", "Happy Dragon Inc."),
    ("hduo", "bubble.pop.games.shooter.ball.game", "Bubble Pop: Ball Shooter Game", "HDuo Fun Games"),
    ("ilyon", "bubbleshooter.orig", "Bubble Shooter - Classic Pop", "Ilyon Dynamics"),
]

# Keyword -> capability. Ordered longest-first so "daily reward" wins over "daily".
SIGNALS = [
    ("daily reward", "daily_reward"),
    ("daily rewards", "daily_reward"),
    ("daily bonus", "daily_reward"),
    ("daily bonuses", "daily_reward"),
    ("colorblind", "colorblind_mode"),
    ("color blind", "colorblind_mode"),
    ("fireball", "fireball_booster"),
    ("fire ball", "fireball_booster"),
    ("bomb", "bomb_booster"),
    ("booster", "boosters"),
    ("boosters", "boosters"),
    ("laser", "laser_aim"),
    ("aim", "aiming"),
    ("combo", "combo_chain"),
    ("consecutive", "combo_chain"),
    ("in a row", "combo_chain"),
    ("leaderboard", "leaderboard"),
    ("achievement", "achievements"),
    ("daily", "daily_challenge"),
    ("offline", "offline"),
    ("no wifi", "offline"),
    ("adventure", "map_adventure"),
    ("episode", "map_adventure"),
    ("map", "map_adventure"),
    ("level", "levels"),
    ("star", "stars"),
    ("reward", "rewards"),
    ("music", "audio"),
    ("sound", "audio"),
    ("effect", "visual_fx"),
    ("animation", "visual_fx"),
    ("pet", "characters"),
    ("cute", "characters"),
    ("obstacle", "obstacles"),
    ("arcade", "arcade_mode"),
    ("classic", "classic_mode"),
    ("props", "boosters"),
    ("coin", "economy"),
    ("purchase", "economy"),
    ("shop", "economy"),
]

METRICS = {
    "rating": r"(\d\.\d)\s*\n?\s*\*?star",
    "downloads": r"(\d[\d.,]*\s*[KMB]?\+)\s*\n?\s*Downloads",
    "reviews": r"([\d.,]+[KMB]?)\s*reviews",
}


def fetch(url: str, timeout: float = 20.0) -> str | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/122 Mobile Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            charset = fh.headers.get_content_charset() or "utf-8"
            return fh.read().decode(charset, "ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(f"  ! {url} -> {type(exc).__name__}: {exc}")
        return None


def html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&amp;", "&").replace("&quot;", '"')
                .replace("&#39;", "'").replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", text)


def analyse(text: str) -> dict:
    low = text.lower()
    found: dict[str, int] = {}
    for keyword, capability in SIGNALS:
        hits = low.count(keyword)
        if hits:
            found[capability] = found.get(capability, 0) + hits
    metrics: dict[str, str] = {}
    for name, pattern in METRICS.items():
        m = re.search(pattern, text, re.I)
        if m:
            metrics[name] = m.group(1).strip()
    return {"capabilities": sorted(found), "signal_counts": found, "metrics": metrics}


def load_snapshot(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="docs")
    ap.add_argument("--snapshot", default="docs/reference_snapshot.json")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot = load_snapshot(Path(args.snapshot))

    results = []
    live = 0
    for key, package, title, developer in REFS:
        url = f"https://play.google.com/store/apps/details?id={package}"
        print(f"\u00b7 {title}")
        html = fetch(url)
        if html:
            text = html_to_text(html)
            analysis = analyse(text)
            analysis.update({"key": key, "package": package, "title": title,
                             "developer": developer, "url": url, "source": "live"})
            live += 1
            if len(text) < 500:
                print("    (page returned too little text, using snapshot)")
                snap = snapshot.get(key)
                if snap:
                    analysis.update(snap)
                    analysis["source"] = "snapshot"
        else:
            snap = snapshot.get(key)
            if not snap:
                print(f"    no route to the store and no snapshot for {key}")
                analysis = {"key": key, "package": package, "title": title, "developer": developer,
                            "url": url, "capabilities": [], "signal_counts": {}, "metrics": {},
                            "source": "unavailable"}
            else:
                analysis = dict(snap)
                analysis.update({"key": key, "package": package, "title": title,
                                 "developer": developer, "url": url, "source": "snapshot"})
        results.append(analysis)
        caps = ", ".join(analysis.get("capabilities", [])) or "\u2014"
        print(f"    source={analysis.get('source')}  capabilities: {caps}")

    union = sorted({c for r in results for c in r.get("capabilities", [])})
    matrix = {
        "generatedBy": "tools/research_probe.py",
        "references": results,
        "capabilityUnion": union,
        "liveFetches": live,
        "note": (
            "Capabilities are keyword signals read from the live store listing, not opinions. "
            "Where the network was blocked the bundled snapshot is used and marked as such."
        ),
    }
    (out_dir / "research_snapshot.json").write_text(json.dumps(matrix, indent=2) + "\n")
    print(f"\n{len(union)} capabilities across {len(results)} references -> {out_dir / 'research_snapshot.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
