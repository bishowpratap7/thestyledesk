# The Style Desk 👗

The best fashion deals are found by communities of sharp-eyed shoppers long before they reach a homepage banner. This desk gathers their finds — sale alerts, frugal dupes, outfit talk and boutique markdowns — into one pretty page, refreshed around the clock.

- Live page: https://bishowpratap7.github.io/thestyledesk/
- Run by **Bishow Pandey** — follow on X: https://x.com/bishowppandey
- Sister desks: The Dev Desk (developer news), Scroll Patrol (trending posts & memes), The World Desk (world news), The Stock Desk (stock deep dives), plus The Shopping Desk, The Cozy Desk, The Foodie Desk and The Style Desk

## What's on the desk
- **🏷️ Sale Finds & Steals**
- **💬 Style Talk & Outfit Questions**
- **👜 Boutique Deals**

Sale finds from r/frugalfemalefashion, style talk from r/femalefashionadvice, and boutique deals from public deal feeds — all linked to the original posts and stores.

## How it works
- `tools/scan.py` reads the public sources above (no API keys), writes `data/feed.json`, bakes an SEO summary of every item into `index.html`, and regenerates `feed.xml` and `sitemap.xml`. If a source fails, the desk keeps its last good data and flags it stale.
- A GitHub Actions loop (`.github/workflows/loop-scan.yml`) re-runs the scanner every 30 minutes around the clock and commits only when something changed; each loop job hands off to its successor, so the desk stays current on its own.
- The page is a single static file — no backend, no build step, no tracking.

## Repos
- `thestyledesk` (public) — the live site, served by GitHub Pages
- `the-style-desk` (private) — the archive twin

## Good to know
Sale prices, sizes and stock change quickly and were accurate only when posted. Photos and posts belong to their creators and communities; every card links to the original. The Style Desk doesn't sell clothing — purchases happen at the stores.
