#!/usr/bin/env python3
"""The Style Desk scanner. Fetches public feeds, writes data/feed.json,
bakes an SEO block + ItemList JSON-LD into index.html, regenerates
feed.xml and sitemap.xml. Per-section failure keeps previous data."""
import json, os, re, subprocess, sys, time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SITE = "https://bishowpratap7.github.io/thestyledesk/"
CONFIG = json.loads(r'''{"sections": {"steals": {"title": "🏷️ Sale Finds & Steals", "type": "reddit", "sub": "frugalfemalefashion", "limit": 12}, "talk": {"title": "💬 Style Talk & Outfit Questions", "type": "reddit", "sub": "femalefashionadvice", "limit": 8}, "boutique": {"title": "👜 Boutique Deals", "type": "slickdeals", "queries": ["dress sale", "women boots", "handbag sale", "jewelry sale", "perfume sale"], "limit": 10}}, "itemlist_name": "Today's style finds and deals on The Style Desk", "feed_title": "The Style Desk — Sale Finds", "feed_desc": "Community-spotted fashion deals and style talk, refreshed around the clock."}''')

def fetch(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        out = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-A", UA, url],
                             capture_output=True, text=True)
        if out.returncode == 0 and out.stdout:
            return out.stdout
        raise

def strip_tags(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", t).strip()

def first_img(html):
    m = re.search(r'<img[^>]+src="([^"]+)"', html or "")
    return m.group(1) if m else ""

def price_of(title):
    m = re.search(r"\$\s?(\d+(?:\.\d{2})?)", title or "")
    return float(m.group(1)) if m else None

def scan_slickdeals(cfg):
    items, seen = [], set()
    for q in cfg["queries"]:
        url = "https://slickdeals.net/newsearch.php?rss=1&searchin=title&q=" + urllib.parse.quote(q) if False else \
              "https://slickdeals.net/newsearch.php?rss=1&searchin=title&q=" + q.replace(" ", "+")
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:
            print(f"  slickdeals '{q}': {e}", file=sys.stderr); continue
        for it in root.iter("item"):
            title = strip_tags(it.findtext("title"))
            link = (it.findtext("link") or "").strip()
            if not title or not link or link in seen:
                continue
            seen.add(link)
            enc = ""
            for ch in it:
                if ch.tag.endswith("encoded"):
                    enc = ch.text or ""
            items.append({"title": title, "url": link, "img": first_img(enc),
                          "price": price_of(title), "source": "Slickdeals community deal",
                          "meta": q})
        time.sleep(0.3)
    cap = cfg.get("max_price")
    if cap:
        cheap = [i for i in items if i["price"] is not None and i["price"] <= cap]
        items = cheap + [i for i in items if i not in cheap]
    return items[: cfg.get("limit", 12)]

def scan_reddit(cfg):
    sub = cfg["sub"]
    raw = fetch(f"https://www.reddit.com/r/{sub}/hot/.rss?limit=30")
    ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(raw)
    items = []
    for e in root.findall("a:entry", ns):
        title = strip_tags(e.findtext("a:title", default="", namespaces=ns))
        link, img = "", ""
        for l in e.findall("a:link", ns):
            if l.get("rel") in (None, "alternate"):
                link = l.get("href", "")
        th = e.find("m:thumbnail", ns)
        if th is not None:
            img = th.get("url", "")
        if not img:
            img = first_img(e.findtext("a:content", default="", namespaces=ns))
        if title and link:
            items.append({"title": title, "url": link, "img": img, "price": None,
                          "source": f"r/{sub}", "meta": "Community post"})
        if len(items) >= cfg.get("limit", 10):
            break
    return items

def scan_mealdb(cfg):
    import random
    cats = cfg["categories"]
    day = datetime.now(timezone.utc).timetuple().tm_yday
    rng = random.Random(day)
    items = []
    picks = [cats[day % len(cats)]] + rng.sample(cats, min(2, len(cats) - 1))
    seen = set()
    for cat in picks:
        try:
            data = json.loads(fetch(f"https://www.themealdb.com/api/json/v1/1/filter.php?c={cat}"))
        except Exception as e:
            print(f"  mealdb {cat}: {e}", file=sys.stderr); continue
        meals = data.get("meals") or []
        rng.shuffle(meals)
        for m in meals[:4]:
            if m["idMeal"] in seen:
                continue
            seen.add(m["idMeal"])
            items.append({"title": m["strMeal"], "img": m.get("strMealThumb", ""),
                          "url": f"https://www.themealdb.com/meal/{m['idMeal']}",
                          "price": None, "source": "TheMealDB", "meta": cat})
    return items[: cfg.get("limit", 10)]

def scan_bank(cfg):
    day = datetime.now(timezone.utc).timetuple().tm_yday
    out = []
    for kind, bank in cfg["banks"].items():
        out.append({"title": bank[day % len(bank)], "url": "", "img": "",
                    "price": None, "source": "The Style Desk", "meta": kind})
    return out

SCANNERS = {"slickdeals": scan_slickdeals, "reddit": scan_reddit,
            "mealdb": scan_mealdb, "bank": scan_bank}

def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def main():
    prev = {}
    pdata = os.path.join(ROOT, "data", "feed.json")
    if os.path.exists(pdata):
        try:
            prev = json.load(open(pdata))
        except Exception:
            prev = {}
    out = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
           "sections": {}}
    for key, cfg in CONFIG["sections"].items():
        try:
            items = SCANNERS[cfg["type"]](cfg)
            if not items:
                raise RuntimeError("empty")
            out["sections"][key] = {"title": cfg["title"], "items": items, "stale": False}
            print(f"{key}: {len(items)} items")
        except Exception as e:
            old = (prev.get("sections") or {}).get(key)
            if old:
                out["sections"][key] = {**old, "stale": True}
                print(f"{key}: FAILED ({e}); kept previous")
            else:
                out["sections"][key] = {"title": cfg["title"], "items": [], "stale": True}
                print(f"{key}: FAILED ({e}); no previous data")
    with open(pdata, "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    bake(out)
    return 0

def bake(out):
    ipath = os.path.join(ROOT, "index.html")
    html = open(ipath).read()
    lines, items, pos = [], [], 1
    for key, sec in out["sections"].items():
        lines.append(f"<h3>{esc(sec['title'])}</h3><ul>")
        for it in sec["items"]:
            price = f" — {('$' + format(it['price'], 'g')) if it.get('price') else ''}" if it.get("price") else ""
            lines.append(f"<li><a href=\"{esc(it['url'])}\">{esc(it['title'])}</a>{price} "
                         f"<span>({esc(it.get('source',''))})</span></li>")
            if it.get("url"):
                items.append({"@type": "ListItem", "position": pos, "name": it["title"][:110], "url": it["url"]})
                pos += 1
        lines.append("</ul>")
    block = "\n".join(lines)
    ld = {"@context": "https://schema.org", "@type": "ItemList",
          "name": CONFIG["itemlist_name"], "itemListElement": items}
    ld_html = '<script type="application/ld+json">\n' + json.dumps(ld, ensure_ascii=False) + "\n</script>"
    new = re.sub(r"<!--FEED:START-->.*?<!--FEED:END-->",
                 "<!--FEED:START-->\n" + block + "\n<!--FEED:END-->", html, flags=re.S)
    new = re.sub(r"<!--ITEMLIST:START-->.*?<!--ITEMLIST:END-->",
                 "<!--ITEMLIST:START-->\n" + ld_html + "\n<!--ITEMLIST:END-->", new, flags=re.S)
    if new != html:
        open(ipath, "w").write(new)
        write_feed(out); write_sitemap(out)
        print("baked: changed")
    else:
        print("baked: unchanged")

def write_feed(out):
    items = ""
    for sec in out["sections"].values():
        for it in sec["items"][:4]:
            if not it.get("url"):
                continue
            items += (f"<item><title>{esc(it['title'])}</title><link>{esc(it['url'])}</link>"
                      f"<guid>{esc(it['url'])}</guid><pubDate>{out['generated_at']}</pubDate></item>\n")
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>{esc(CONFIG['feed_title'])}</title><link>{SITE}</link>"
            f"<description>{esc(CONFIG['feed_desc'])}</description>\n" + items + "</channel></rss>")
    open(os.path.join(ROOT, "feed.xml"), "w").write(feed)

def write_sitemap(out):
    sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          f"<url><loc>{SITE}</loc><lastmod>{out['generated_at']}</lastmod>"
          "<changefreq>hourly</changefreq><priority>1.0</priority></url></urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write(sm)

if __name__ == "__main__":
    sys.exit(main())
