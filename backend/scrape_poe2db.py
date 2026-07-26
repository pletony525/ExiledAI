import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://poe2db.tw"
USER_AGENT = "Mozilla/5.0 (compatible; POE2AdvisorBot/0.1; personal research project)"
RATE_LIMIT_SECONDS = 1.0
RAW_DIR = Path(__file__).parent / "data" / "raw"

CATEGORY_PATHS = [
    "/us/Claws", "/us/Daggers", "/us/Wands", "/us/One_Hand_Swords", "/us/One_Hand_Axes",
    "/us/One_Hand_Maces", "/us/Sceptres", "/us/Spears", "/us/Flails",
    "/us/Bows", "/us/Staves", "/us/Two_Hand_Swords", "/us/Two_Hand_Axes",
    "/us/Two_Hand_Maces", "/us/Quarterstaves", "/us/Crossbows", "/us/Traps", "/us/Talismans",
    "/us/Quivers", "/us/Bucklers", "/us/Foci",
    "/us/Amulets", "/us/Rings", "/us/Belts",
    "/us/Life_Flasks", "/us/Mana_Flasks", "/us/Charms",
    # Armour category pages don't host mod data themselves - poe2db splits armour mods
    # by attribute-requirement subtype (str/dex/int/combinations), each with its own
    # #ModifiersCalc page. e.g. /us/Gloves has no mod calculator; /us/Gloves_str does.
    "/us/Gloves_str", "/us/Gloves_dex", "/us/Gloves_int",
    "/us/Gloves_str_dex", "/us/Gloves_str_int", "/us/Gloves_dex_int",
    "/us/Boots_str", "/us/Boots_dex", "/us/Boots_int",
    "/us/Boots_str_dex", "/us/Boots_str_int", "/us/Boots_dex_int",
    "/us/Body_Armours_str", "/us/Body_Armours_dex", "/us/Body_Armours_int",
    "/us/Body_Armours_str_dex", "/us/Body_Armours_str_int", "/us/Body_Armours_dex_int",
    "/us/Body_Armours_str_dex_int",
    "/us/Helmets_str", "/us/Helmets_dex", "/us/Helmets_int",
    "/us/Helmets_str_dex", "/us/Helmets_str_int", "/us/Helmets_dex_int",
    "/us/Shields_str", "/us/Shields_str_dex", "/us/Shields_str_int",
    # Jewels are organized by gem color, not a generic "Jewels" page.
    "/us/Ruby", "/us/Emerald", "/us/Sapphire", "/us/Diamond",
]

NAV_LINK_EXCLUDE = {
    "/us/", "/us/Act", "/us/Ascendancy_class", "/us/Items", "/us/Unique_item",
    "/us/Gem", "/us/Skill_Gems", "/us/Support_Gems", "/us/Spirit_Gems",
    "/us/Modifiers", "/us/EndGame", "/us/pob", "/us/account",
    "/us/Crafting", "/us/Desecrated_Modifiers", "/us/Keywords", "/us/Lineage_Supports",
    "/us/Liquid_Emotions", "/us/Quest", "/us/Waystones", "/us/patreon",
}


def fetch(path, retries=3):
    time.sleep(RATE_LIMIT_SECONDS)
    for attempt in range(retries):
        try:
            resp = requests.get(f"{BASE}{path}", headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def slugify(path):
    return path.strip("/").split("/")[-1]


def already_scraped(subdir, slug):
    return (RAW_DIR / subdir / f"{slug}.json").exists()


def save_json(subdir, slug, data):
    out_dir = RAW_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return out_path


def extract_links(html):
    hrefs = set(re.findall(r'href="(/us/[A-Za-z0-9_]+)"', html))
    return sorted(h for h in hrefs if h not in NAV_LINK_EXCLUDE)


def extract_balanced_json(html, marker):
    """Find `marker` then extract the first balanced {...} JSON object that follows,
    respecting string literals so braces inside quoted strings don't confuse depth counting."""
    start = html.find(marker)
    if start == -1:
        return None
    start = html.find("{", start)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
    return None


def scrape_unique_page(path, force=False):
    slug = slugify(path)
    if not force and already_scraped("uniques", slug):
        return "skipped"
    html = fetch(path)
    raw = extract_balanced_json(html, "white-space-collapse: preserve")
    if raw is None:
        return "no_json"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "parse_error"
    data["_source_url"] = f"{BASE}{path}"
    save_json("uniques", slug, data)
    return "ok"


def scrape_gem_page(path, subdir, force=False):
    slug = slugify(path)
    if not force and already_scraped(subdir, slug):
        return "skipped"
    html = fetch(path)
    soup = BeautifulSoup(html, "lxml")
    content_div = soup.select_one(".newItemPopup .content")
    if content_div is None:
        return "no_content"
    record = {
        "name": slug.replace("_", " "),
        "source_url": f"{BASE}{path}",
        "content_html": str(content_div),
    }
    save_json(subdir, slug, record)
    return "ok"


def scrape_category_mods(path, force=False):
    slug = slugify(path)
    if not force and already_scraped("mods", slug):
        return "skipped"
    html = fetch(path)
    raw = extract_balanced_json(html, "new ModsView(")
    if raw is None:
        return "no_json"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "parse_error"
    record = {
        "category": data.get("baseitem", {}).get("href", slug),
        "source_url": f"{BASE}{path}",
        "mods": data.get("normal", []),
    }
    save_json("mods", slug, record)
    return "ok"


def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"  ERROR: {e}")
        return "error"


def run(kinds, force=False, limit=None):
    counts = {}

    def bump(status):
        counts[status] = counts.get(status, 0) + 1

    if "uniques" in kinds:
        print("Fetching unique item index...")
        links = extract_links(fetch("/us/Unique_item"))
        if limit:
            links = links[:limit]
        print(f"{len(links)} candidate unique pages")
        for i, path in enumerate(links, 1):
            status = safe_call(scrape_unique_page, path, force=force)
            bump(f"uniques:{status}")
            print(f"[{i}/{len(links)}] unique {path} -> {status}")

    if "skill_gems" in kinds:
        print("Fetching skill gem index...")
        links = extract_links(fetch("/us/Skill_Gems"))
        if limit:
            links = links[:limit]
        print(f"{len(links)} candidate skill gem pages")
        for i, path in enumerate(links, 1):
            status = safe_call(scrape_gem_page, path, "skill_gems", force=force)
            bump(f"skill_gems:{status}")
            print(f"[{i}/{len(links)}] skill_gem {path} -> {status}")

    if "support_gems" in kinds:
        print("Fetching support gem index...")
        links = extract_links(fetch("/us/Support_Gems"))
        if limit:
            links = links[:limit]
        print(f"{len(links)} candidate support gem pages")
        for i, path in enumerate(links, 1):
            status = safe_call(scrape_gem_page, path, "support_gems", force=force)
            bump(f"support_gems:{status}")
            print(f"[{i}/{len(links)}] support_gem {path} -> {status}")

    if "mods" in kinds:
        paths = CATEGORY_PATHS[:limit] if limit else CATEGORY_PATHS
        print(f"{len(paths)} category pages for mod tables")
        for i, path in enumerate(paths, 1):
            status = safe_call(scrape_category_mods, path, force=force)
            bump(f"mods:{status}")
            print(f"[{i}/{len(paths)}] mods {path} -> {status}")

    print("\nSummary:", counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        choices=["uniques", "skill_gems", "support_gems", "mods", "all"],
        default="all",
    )
    parser.add_argument("--force", action="store_true", help="re-scrape even if output file exists")
    parser.add_argument("--limit", type=int, default=None, help="cap number of pages per category, for testing")
    args = parser.parse_args()

    kinds = ["uniques", "skill_gems", "support_gems", "mods"] if args.only == "all" else [args.only]
    run(kinds, force=args.force, limit=args.limit)
