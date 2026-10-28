"""Diagnostic: check tables, try inserting a translation, verify persistence."""

import os
from sqlalchemy import create_engine, inspect, text

url = os.environ.get("DATABASE_URL")
print(f"DATABASE_URL: {url}")

engine = create_engine(url)

# Check all tables
insp = inspect(engine)
tables = sorted(insp.get_table_names())
print(f"\nTables ({len(tables)}):")
for t in tables:
    cols = [c["name"] for c in insp.get_columns(t)]
    print(f"  {t}: {cols}")

# Check if translation table exists
if "translation" in tables:
    with engine.connect() as conn:
        r = conn.execute(text("SELECT count(*) FROM translation"))
        print(f"\ntranslation count: {r.scalar()}")

        # Try inserting a row and committing
        print("\nAttempting to insert a test translation...")
        conn.execute(
            text(
                "INSERT INTO translation (locale, namespace, key, value, created_at, updated_at) "
                "VALUES ('en-GB', 'test', 'test.key', 'test value', NOW(), NOW())"
            )
        )
        conn.commit()
        print("Insert + commit succeeded.")

        r = conn.execute(text("SELECT count(*) FROM translation"))
        print(f"translation count after insert: {r.scalar()}")
else:
    print("\ntranslation table does NOT exist!")
