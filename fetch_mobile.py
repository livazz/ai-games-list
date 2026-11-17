#!/usr/bin/env python3
"""Mobile : il n'existe aucune étiquette IA sur l'App Store ni sur Google Play.

1. Pour chaque jeu Steam qui déclare de l'IA, cherche une version iPhone (API de recherche iTunes,
   même titre et même éditeur). La déclaration reste celle de la fiche Steam.
2. Relève les classements App Store US (jeux les plus rentables, jeux gratuits) pour situer chaque jeu.

Écrit data/mobile_raw.json (repris là où il s'est arrêté).
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "steam_raw.json"
OUT = ROOT / "data" / "mobile_raw.json"
STOP = {"games", "game", "inc", "ltd", "llc", "studio", "studios", "entertainment", "co", "limited", "the",
        "interactive", "corporation", "corp", "gmbh", "pte", "sa", "ab", "oy", "digital", "publishing", "of"}


def get(url):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8"}), timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            print(f"  nouvel essai dans {30 * (i + 1)}s ({e})", flush=True)
            time.sleep(30 * (i + 1))
    return None


def norm(s):
    s = re.sub(r"[®™©]", "", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def words(s):
    return {w for w in norm(s).split() if w not in STOP and len(w) > 1}


def charts():
    res = {}
    for key, feed in (("grossing", "topgrossingapplications"), ("free", "topfreeapplications"), ("paid", "toppaidapplications")):
        d = get(f"https://itunes.apple.com/us/rss/{feed}/limit=200/genre=6014/json")
        res[key] = [e["id"]["attributes"]["im:id"] for e in d["feed"]["entry"]] if d else []
    return res


def main():
    steam = json.loads(RAW.read_text())
    data = json.loads(OUT.read_text()) if OUT.exists() else {"matches": {}}
    data["fetched"] = time.strftime("%Y-%m-%d")
    data["charts"] = charts()
    todo = [g for g in steam["games"] if steam["pages"].get(g["appid"], {}).get("ai") and g["appid"] not in data["matches"]]
    print(f"jeux à chercher sur l'App Store : {len(todo)}", flush=True)
    for n, g in enumerate(todo, 1):
        p = steam["pages"][g["appid"]]
        q = urllib.parse.quote(re.sub(r"[®™©]", "", g["title"]))
        d = get(f"https://itunes.apple.com/search?term={q}&entity=software&country=us&limit=8")
        hit = None
        makers = words(p.get("developer", "")) | words(p.get("publisher", ""))
        base = norm(g["title"])
        for r in (d or {}).get("results", []):
            if "Games" not in r.get("genres", []):
                continue
            name = norm(r["trackName"])
            same_title = name == base or name.startswith(base + " ") or base.startswith(name + " ")
            if same_title and makers & words(r.get("sellerName", "") + " " + r.get("artistName", "")):
                hit = {"id": str(r["trackId"]), "name": r["trackName"], "seller": r.get("sellerName", ""),
                       "url": r["trackViewUrl"].split("?")[0], "ratings": r.get("userRatingCount"),
                       "rating": r.get("averageUserRating"), "price": r.get("formattedPrice", "")}
                break
        data["matches"][g["appid"]] = hit
        if n % 10 == 0 or n == len(todo):
            found = sum(1 for v in data["matches"].values() if v)
            print(f"App Store : {n}/{len(todo)} — versions iPhone trouvées : {found}", flush=True)
            OUT.write_text(json.dumps(data, ensure_ascii=False))
        time.sleep(3.2)  # l'API iTunes limite à environ 20 recherches par minute
    OUT.write_text(json.dumps(data, ensure_ascii=False))
    print("TERMINÉ", flush=True)


if __name__ == "__main__":
    main()
