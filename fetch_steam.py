#!/usr/bin/env python3
"""Top sellers Steam + déclaration « AI Generated Content Disclosure » de chaque fiche.

Sources :
- classement : https://store.steampowered.com/search/?filter=topsellers&category1=998 (pays US)
- déclaration : section « AI Generated Content Disclosure » de la fiche de chaque jeu

Écrit data/steam_raw.json (repris là où il s'est arrêté).
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "steam_raw.json"
TOP = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
COOKIE = "birthtime=0; wants_mature_content=1; lastagecheckage=1-0-1990; Steam_Language=english"


def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Cookie": COOKIE})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace"), r.geturl()
        except Exception as e:  # 429, coupure…
            wait = 20 * (i + 1)
            print(f"  nouvel essai dans {wait}s ({e})", flush=True)
            time.sleep(wait)
    return None, None


ROW = re.compile(r'<a href="(https://store\.steampowered\.com/app/(\d+)/[^"?]*)[^>]*?class="search_result_row.*?</a>', re.S)


def ranking():
    games, start = [], 0
    while len(games) < TOP:
        txt, _ = get(f"https://store.steampowered.com/search/results/?query&start={start}&count=100"
                     "&filter=topsellers&category1=998&infinite=1&cc=us&l=english")
        if not txt:
            break
        h = json.loads(txt)["results_html"]
        rows = ROW.findall(h)
        blocks = [m.group(0) for m in ROW.finditer(h)]
        if not blocks:
            break
        for (url, appid), b in zip(rows, blocks):
            if any(g["appid"] == appid for g in games):
                continue
            title = re.search(r'<span class="title">(.*?)</span>', b, re.S)
            rel = re.search(r'search_released[^>]*>\s*(.*?)\s*</div>', b, re.S)
            rev = re.search(r'(\d+)% of the ([\d,]+) user reviews', b)
            price = re.search(r'data-price-final="(\d+)"', b)
            games.append({
                "rank": len(games) + 1,
                "appid": appid,
                "url": url,
                "title": html.unescape(title.group(1)) if title else "",
                "released": rel.group(1) if rel else "",
                "review_pct": int(rev.group(1)) if rev else None,
                "reviews": int(rev.group(2).replace(",", "")) if rev else None,
                "price_usd": int(price.group(1)) / 100 if price else None,
            })
        start += 100
        print(f"classement : {len(games)} jeux", flush=True)
        time.sleep(1)
    return games[:TOP]


DISC = re.compile(r'AI Generated Content Disclosure</h2>.*?<i>(.*?)</i>', re.S)


def disclosure(g):
    txt, final = get(f"https://store.steampowered.com/app/{g['appid']}/?l=english&cc=us")
    if txt is None:
        return g["appid"], {"status": "error"}
    if f"/app/{g['appid']}" not in (final or ""):
        return g["appid"], {"status": "redirect"}
    m = DISC.search(txt)
    dev = re.findall(r'<div class="dev_row">.*?</div>\s*</div>', txt, re.S)
    devs = []
    for d in dev[:2]:
        devs.append(", ".join(html.unescape(x) for x in re.findall(r'<a [^>]*>(.*?)</a>', d)))
    text = None
    if m:
        text = re.sub(r"<br\s*/?>", "\n", m.group(1))
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    return g["appid"], {"status": "ok", "ai": text, "developer": devs[0] if devs else "",
                        "publisher": devs[1] if len(devs) > 1 else ""}


def main():
    OUT.parent.mkdir(exist_ok=True)
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    if not data.get("games"):
        data = {"fetched": time.strftime("%Y-%m-%d"), "games": ranking(), "pages": {}}
        OUT.write_text(json.dumps(data, ensure_ascii=False))
    todo = [g for g in data["games"] if data["pages"].get(g["appid"], {}).get("status") not in ("ok", "redirect")]
    print(f"fiches à lire : {len(todo)}", flush=True)
    done = 0
    with ThreadPoolExecutor(3) as ex:
        for appid, res in ex.map(disclosure, todo):
            data["pages"][appid] = res
            done += 1
            if done % 50 == 0 or done == len(todo):
                n_ai = sum(1 for p in data["pages"].values() if p.get("ai"))
                print(f"fiches : {done}/{len(todo)} — avec déclaration IA : {n_ai}", flush=True)
                OUT.write_text(json.dumps(data, ensure_ascii=False))
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    print("TERMINÉ", flush=True)


if __name__ == "__main__":
    main()
