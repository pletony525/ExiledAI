import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not set (checked environment and .env)", file=sys.stderr)
    sys.exit(1)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

with open(SCHEMA_PATH) as f:
    schema_sql = f.read()

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()

print("Schema applied.")
