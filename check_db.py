import sqlite3
import os

# Try both possible locations
for path in ['instance/climbs.db', 'climbs.db']:
    if os.path.exists(path):
        conn = sqlite3.connect(path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"Found DB at: {path}")
        print("Tables:", [t[0] for t in tables])
        conn.close()
        break
else:
    print("Database not found in instance/ or root directory")