import json
import os
import re
import sys
from pathlib import Path

import psycopg
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from psycopg.types.json import Json

load_dotenv()

RAW_DIR = Path(__file__).parent / "data" / "raw"
EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 100

BRACKET_PIPE_RE = re.compile(r"\[([^|\]]+)\|([^\]]+)\]")
BRACKET_RE = re.compile(r"\[([^\]]+)\]")
GEM_SELECTORS = ".property, .requirements, .secDescrText, .description, .explicitMod, .qualityMod, .secondaryQualityMod"
MOD_GENERATION_TYPES = {"1": "Prefix", "2": "Suffix"}


def clean_text(s):
    if not s:
        return ""
    s = BRACKET_PIPE_RE.sub(lambda m: m.group(2), s)
    s = BRACKET_RE.sub(lambda m: m.group(1), s)
    return s


def tidy_spacing(s):
    s = re.sub(r"\s+([,.;:%])", r"\1", s)
    return re.sub(r" {2,}", " ", s)


def clean_html(s):
    if not s:
        return ""
    return tidy_spacing(clean_text(BeautifulSoup(s, "lxml").get_text(" ", strip=True)))


def format_values(prop):
    vals = prop.get("values") or []
    return ", ".join(v[0] for v in vals if isinstance(v, list) and v)


def unique_to_chunk(data):
    name = data.get("name", "")
    type_line = data.get("typeLine", "")
    lines = [f"{name} ({type_line}) - Unique Item"]

    for prop in data.get("properties", []):
        pname = clean_text(prop.get("name", ""))
        pvals = format_values(prop)
        if pname and pvals:
            lines.append(f"{pname}: {pvals}")
        elif pname:
            lines.append(pname)

    req_parts = []
    for r in data.get("requirements", []):
        rname = clean_text(r.get("name", ""))
        rvals = format_values(r)
        if rname == "Level":
            req_parts.append(f"Level {rvals}")
        else:
            req_parts.append(f"{rvals} {rname}".strip())
    if req_parts:
        lines.append("Requires: " + ", ".join(req_parts))

    for mod in data.get("implicitMods") or []:
        lines.append(clean_text(mod))
    for mod in data.get("explicitMods") or []:
        lines.append(clean_text(mod))
    for ft in data.get("flavourText") or []:
        lines.append(f'"{clean_text(ft)}"')

    content = "\n".join(lines)
    metadata = {
        "item_name": name,
        "source_url": data.get("_source_url"),
        "content_type": "unique_item",
        "base_type": data.get("baseType"),
        "ilvl": data.get("ilvl"),
    }
    return content, metadata


def gem_to_chunk(data, kind):
    label = "Skill Gem" if kind == "skill_gems" else "Support Gem"
    lines = [f"{data['name']} ({label})"]
    soup = BeautifulSoup(data["content_html"], "lxml")
    for el in soup.select(GEM_SELECTORS):
        text = el.get_text(" ", strip=True)
        if text:
            lines.append(tidy_spacing(clean_text(text)))

    content = "\n".join(lines)
    metadata = {
        "item_name": data["name"],
        "source_url": data["source_url"],
        "content_type": "skill_gem" if kind == "skill_gems" else "support_gem",
    }
    return content, metadata


def load_deduped_mods():
    """Mods repeat across category files (e.g. the same affix can spawn on
    both Claws and Daggers). Dedupe by the `hover` field, a stable
    content-derived hash id poe2db assigns per mod, merging spawn_no and
    category lists from every file the mod appeared in."""
    merged = {}
    for path in sorted((RAW_DIR / "mods").glob("*.json")):
        data = json.loads(path.read_text())
        category = data.get("category", path.stem)
        for mod in data.get("mods", []):
            key = mod.get("hover") or (mod.get("Name"), mod.get("Level"), mod.get("ModGenerationTypeID"))
            if key not in merged:
                merged[key] = {**mod, "_categories": set(), "_spawn": set(mod.get("spawn_no") or [])}
            merged[key]["_categories"].add(category)
            merged[key]["_spawn"].update(mod.get("spawn_no") or [])
    return list(merged.values())


def mod_to_chunk(mod):
    gen_type = MOD_GENERATION_TYPES.get(mod.get("ModGenerationTypeID"), "")
    name = mod.get("Name", "")
    lines = [f"{name} ({gen_type} mod)".strip()]

    desc = clean_html(mod.get("str", ""))
    if desc:
        lines.append(desc)

    fam = mod.get("ModFamilyList") or []
    if fam:
        lines.append("Mod family: " + ", ".join(fam))

    lines.append(f"Minimum item level: {mod.get('Level', '?')}")

    spawn = sorted(mod.get("_spawn") or [])
    if spawn:
        lines.append("Can roll on: " + ", ".join(spawn))

    content = "\n".join(lines)
    metadata = {
        "mod_name": name,
        "content_type": "mod",
        "generation_type": gen_type,
        "categories": sorted(mod.get("_categories") or []),
    }
    return content, metadata


def build_all_chunks():
    chunks = []  # list of (source, content, metadata)

    for path in sorted((RAW_DIR / "uniques").glob("*.json")):
        data = json.loads(path.read_text())
        content, metadata = unique_to_chunk(data)
        chunks.append((data.get("_source_url", path.stem), content, metadata))

    for kind in ("skill_gems", "support_gems"):
        for path in sorted((RAW_DIR / kind).glob("*.json")):
            data = json.loads(path.read_text())
            content, metadata = gem_to_chunk(data, kind)
            chunks.append((data["source_url"], content, metadata))

    for mod in load_deduped_mods():
        content, metadata = mod_to_chunk(mod)
        source = mod.get("hover") or f"mod:{mod.get('Name')}:{mod.get('Level')}"
        chunks.append((source, content, metadata))

    return chunks


def embed_and_insert(chunks, database_url, openai_api_key):
    client = OpenAI(api_key=openai_api_key)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE chunks")
        conn.commit()

        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[i : i + EMBED_BATCH_SIZE]
            texts = [c[1] for c in batch]
            response = client.embeddings.create(model=EMBED_MODEL, input=texts)

            rows = []
            for (source, content, metadata), item in zip(batch, response.data):
                vector_literal = "[" + ",".join(f"{x:.7f}" for x in item.embedding) + "]"
                rows.append((source, content, vector_literal, Json(metadata)))

            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (source, content, embedding, metadata) VALUES (%s, %s, %s::vector, %s)",
                    rows,
                )
            conn.commit()
            print(f"embedded + inserted {min(i + EMBED_BATCH_SIZE, len(chunks))}/{len(chunks)}")


if __name__ == "__main__":
    chunks = build_all_chunks()
    print(f"Built {len(chunks)} chunks from raw data.")

    if "--preview" in sys.argv:
        for source, content, metadata in chunks[:5]:
            print("=" * 60)
            print("source:", source)
            print("metadata:", metadata)
            print(content)
        sys.exit(0)

    database_url = os.environ.get("DATABASE_URL")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url or not openai_api_key:
        print("DATABASE_URL and OPENAI_API_KEY must both be set (env or .env)", file=sys.stderr)
        sys.exit(1)

    embed_and_insert(chunks, database_url, openai_api_key)
    print("Done.")
