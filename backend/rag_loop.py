import os
import re
import sys

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 5

SYSTEM_PROMPT = """You are a Path of Exile 2 build and trade advisor. Answer the \
user's question using ONLY the context chunks below, which come from a database \
of POE2 unique items, skill gems, support gems, and item modifiers.

If the context does not contain enough information to answer confidently, say so \
explicitly rather than guessing - do not use outside knowledge about Path of Exile 2 \
beyond what's in the context. Cite specific item/gem/mod names from the context when \
relevant."""


def retrieve(cur, question_embedding, top_k=TOP_K):
    vector_literal = "[" + ",".join(f"{x:.7f}" for x in question_embedding) + "]"
    cur.execute(
        """
        SELECT source, content, metadata, embedding <=> %s::vector AS distance
        FROM chunks
        ORDER BY distance
        LIMIT %s
        """,
        (vector_literal, top_k),
    )
    return cur.fetchall()


def build_prompt(question, chunks):
    context = "\n---\n".join(content for _, content, _, _ in chunks)
    return f"Context:\n---\n{context}\n---\n\nQuestion: {question}"


def load_entity_names(cur):
    """Names of uniques/gems for the exact-match fallback below. Mods are excluded -
    their names (e.g. "Sturdy", "Resilient") are too generic/short and would cause
    false-positive matches against unrelated questions."""
    cur.execute(
        """
        SELECT source, metadata->>'item_name' AS name
        FROM chunks
        WHERE metadata->>'content_type' IN ('unique_item', 'skill_gem', 'support_gem')
        """
    )
    return cur.fetchall()


def find_named_entity_match(question, entity_names):
    """Dense vector search alone can miss a specific named entity even when its chunk
    is perfectly good (confirmed during Step 4 testing - e.g. Astramentis, Abyssal Pact
    didn't surface in top-5 despite complete data). This exact/word-boundary match is a
    cheap, purely additive fallback: it can only add a relevant chunk, never remove one."""
    q_lower = question.lower()
    best = None
    for source, name in entity_names:
        if not name:
            continue
        pattern = r"\b" + re.escape(name.lower()) + r"\b"
        if re.search(pattern, q_lower) and (best is None or len(name) > len(best[1])):
            best = (source, name)
    return best


def fetch_chunk_by_source(cur, source):
    cur.execute("SELECT source, content, metadata, 0.0 FROM chunks WHERE source = %s", (source,))
    return cur.fetchone()


def answer_question(client, cur, question, entity_names):
    embedding = client.embeddings.create(model=EMBED_MODEL, input=[question]).data[0].embedding
    chunks = retrieve(cur, embedding)

    match = find_named_entity_match(question, entity_names)
    if match and not any(c[0] == match[0] for c in chunks):
        exact_chunk = fetch_chunk_by_source(cur, match[0])
        if exact_chunk:
            chunks = [exact_chunk] + chunks

    print("\nRetrieved:")
    for source, _, metadata, distance in chunks:
        name = metadata.get("item_name") or metadata.get("mod_name") or source
        tag = " [exact-match]" if match and source == match[0] else ""
        print(f"  [{distance:.3f}] ({metadata.get('content_type')}) {name}{tag}")

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(question, chunks)},
        ],
    )
    print("\nAnswer:")
    print(response.choices[0].message.content)


def main():
    database_url = os.environ.get("DATABASE_URL")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url or not openai_api_key:
        print("DATABASE_URL and OPENAI_API_KEY must both be set (env or .env)", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=openai_api_key)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            entity_names = load_entity_names(cur)

            if len(sys.argv) > 1:
                answer_question(client, cur, " ".join(sys.argv[1:]), entity_names)
                return

            print("POE2 Advisor - ask a question (blank line or Ctrl-D to quit)")
            while True:
                try:
                    question = input("\n> ").strip()
                except EOFError:
                    break
                if not question:
                    break
                answer_question(client, cur, question, entity_names)


if __name__ == "__main__":
    main()
