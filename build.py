#!/usr/bin/env python3
"""Fabrique docs/index.html (page filtrable) et README.md (tableaux lisibles sur GitHub)."""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from classify import category, classify

ROOT = Path(__file__).resolve().parent
steam = json.loads((ROOT / "data" / "steam_raw.json").read_text())
mob_path = ROOT / "data" / "mobile_raw.json"
mob = json.loads(mob_path.read_text()) if mob_path.exists() else {"matches": {}, "charts": {}}
charts = mob.get("charts", {})

FLAGS = ["code", "visuals", "audio", "text", "live", "marketing"]
LABEL = {"code": "Code", "visuals": "Visuels", "audio": "Son et voix", "text": "Texte et traduction",
         "live": "IA pendant le jeu", "marketing": "Page du store"}
CAT_LABEL = {"code+visuels": "Code et visuels", "code": "Code, sans visuels", "visuels": "Visuels, sans code",
             "autre": "Autre usage (son, texte, IA en jeu)", "non précisé": "Usage non précisé"}


def chart_rank(ios_id):
    out = {}
    for k in ("grossing", "free", "paid"):
        ids = charts.get(k, [])
        if ios_id in ids:
            out[k] = ids.index(ios_id) + 1
    return out


def play_link(title):
    return "https://play.google.com/store/search?c=apps&q=" + urllib.parse.quote(title)


# ---------- Steam
steam_rows, read = [], 0
for g in steam["games"]:
    p = steam["pages"].get(g["appid"], {})
    if p.get("status") == "ok":
        read += 1
    if not p.get("ai"):
        continue
    f = classify(p["ai"], g["appid"])
    steam_rows.append({
        "rank": g["rank"], "title": g["title"], "url": f"https://store.steampowered.com/app/{g['appid']}/",
        "maker": p.get("developer") or p.get("publisher") or "", "released": g["released"],
        "reviews": g["reviews"], "pct": g["review_pct"], "price": g["price_usd"],
        "flags": [k for k in FLAGS if f[k]], "cat": category(f), "appid": g["appid"],
    })

# ---------- Mobile
mobile_rows = []
curated = json.loads((ROOT / "mobile_curated.json").read_text())
ids = ",".join(c["ios_id"] for c in curated if c.get("ios_id"))
look = {}
try:
    with urllib.request.urlopen(f"https://itunes.apple.com/lookup?id={ids}&country=us", timeout=30) as r:
        look = {str(x["trackId"]): x for x in json.loads(r.read())["results"]}
except Exception as e:
    print("lookup App Store impossible :", e)
seen = set()
for c in curated:
    f = {k: bool(c["flags"].get(k)) for k in FLAGS}
    info = look.get(c.get("ios_id", ""), {})
    seen.add(c.get("ios_id"))
    mobile_rows.append({
        "title": c["title"], "url": c["url"], "maker": c["maker"], "ratings": info.get("userRatingCount"),
        "charts": chart_rank(c.get("ios_id", "")), "flags": [k for k in FLAGS if f[k]], "cat": category(f),
        "proof": "presse", "note": c["note"], "source": c["source"], "source_url": c["source_url"],
        "play": None if c.get("web") else play_link(c["title"]), "web": bool(c.get("web")),
    })
by_app = {r["appid"]: r for r in steam_rows}
# même nom mais autre jeu (version mobile distincte, application compagnon) : la déclaration Steam ne s'y applique pas
OTHER_GAME = ("Companion", "Arcade Edition", "Call of Duty®: Mobile", "Blitz", "MapleStory M", "Solo Leveling:Arise")
for appid, m in mob.get("matches", {}).items():
    if not m or m["id"] in seen or appid not in by_app or any(x in m["name"] for x in OTHER_GAME):
        continue
    s = by_app[appid]
    mobile_rows.append({
        "title": m["name"], "url": m["url"], "maker": m["seller"], "ratings": m.get("ratings"),
        "charts": chart_rank(m["id"]), "flags": s["flags"], "cat": s["cat"], "proof": "steam",
        "note": f"Le même jeu déclare de l'IA sur sa fiche Steam (rang {s['rank']} des ventes Steam). "
                "La déclaration porte sur la version PC.",
        "source": "Déclaration sur Steam", "source_url": s["url"], "play": play_link(s["title"]), "web": False,
    })
mobile_rows.sort(key=lambda r: -(r["ratings"] or 0))

meta = {"date": steam.get("fetched", time.strftime("%Y-%m-%d")), "top": len(steam["games"]), "read": read,
        "steam_ai": len(steam_rows), "mobile_date": mob.get("fetched", time.strftime("%Y-%m-%d"))}
data = {"meta": meta, "steam": steam_rows, "mobile": mobile_rows, "labels": LABEL, "cats": CAT_LABEL}

tpl = (ROOT / "template.html").read_text()
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "index.html").write_text(tpl.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))


# ---------- README
def n(x):
    return f"{x:,}".replace(",", " ") if x is not None else "—"


def uses(r):
    return ", ".join(LABEL[k] for k in r["flags"]) or "Non précisé"


L = ["# Jeux faits avec de l'IA : les meilleures ventes", "",
     "**Page filtrable (code, visuels, les deux) : https://livazz.github.io/ai-games-list/**", "",
     f"Relevé du {meta['date']}. Steam : les {n(meta['top'])} meilleures ventes du moment (classement officiel de Steam, "
     f"boutique des États-Unis), dont **{n(meta['steam_ai'])} jeux déclarent de l'IA générative** sur leur fiche.", "",
     "## D'où viennent les données", "",
     "- **Classement** : [meilleures ventes Steam](https://store.steampowered.com/search/?filter=topsellers&category1=998), "
     "classées par Steam selon le chiffre d'affaires récent. Le nombre d'avis donne une idée des ventes sur la durée.",
     "- **Usage de l'IA** : la rubrique « AI Generated Content Disclosure » que chaque studio remplit lui-même sur sa fiche Steam. "
     "Le tri par usage (code, visuels, son, texte, IA pendant le jeu) est fait par mots-clés sur ce texte : il peut se tromper, "
     "le lien de chaque jeu mène à la déclaration d'origine.",
     "- **Limite** : un studio qui ne déclare rien n'apparaît pas, et beaucoup d'usages du code ne sont pas déclarés "
     "(Steam ne demande de déclarer que ce qui se retrouve dans le jeu).",
     "- **Mobile** : ni l'App Store ni Google Play n'affichent d'étiquette IA. La liste mobile réunit donc "
     "(1) des jeux dont l'usage de l'IA est confirmé par le créateur ou la presse, source en lien, et "
     "(2) les jeux de la liste Steam qui existent aussi sur iPhone. Classements App Store : flux officiels d'Apple (États-Unis).", ""]
for cat in ["code+visuels", "code", "visuels", "autre", "non précisé"]:
    rows = [r for r in steam_rows if r["cat"] == cat]
    L += [f"## Steam — {CAT_LABEL[cat]} ({len(rows)})", "", "| Rang ventes | Jeu | Studio | Avis | Usages déclarés |", "|--:|---|---|--:|---|"]
    for r in rows:
        L.append(f"| {r['rank']} | [{r['title'].replace('|', '/')}]({r['url']}) | {r['maker'].replace('|', '/')} | {n(r['reviews'])} | {uses(r)} |")
    L.append("")
L += [f"## Mobile ({len(mobile_rows)})", "", "| Jeu | Éditeur | Notes App Store (US) | Usages | Preuve |", "|---|---|--:|---|---|"]
for r in mobile_rows:
    L.append(f"| [{r['title'].replace('|', '/')}]({r['url']}) | {r['maker'].replace('|', '/')} | {n(r['ratings'])} | {uses(r)} | [{r['source']}]({r['source_url']}) |")
L += ["", "## Mettre à jour", "", "```bash", "python3 fetch_steam.py 3000 && python3 fetch_mobile.py && python3 build.py", "```", ""]
(ROOT / "README.md").write_text("\n".join(L))
from collections import Counter
print(meta, Counter(r["cat"] for r in steam_rows), "mobile:", len(mobile_rows))
