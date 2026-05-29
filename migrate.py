"""
One-shot migration script — adds any missing columns to an existing database.
Safe to run multiple times (checks before altering).

Usage:  python3 migrate.py
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data", "ledplayer.db")

if not os.path.exists(DB_PATH):
    print("No database found — nothing to migrate (it will be created fresh on first run).")
    exit(0)

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

migrations = [
    # (table, column, definition)
    ("playlist_items", "loop", "INTEGER NOT NULL DEFAULT 0"),
]

for table, column, definition in migrations:
    cur.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cur.fetchall()]
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"  Added column: {table}.{column}")
    else:
        print(f"  Already exists, skipping: {table}.{column}")

conn.commit()
conn.close()
print("Migration complete.")
