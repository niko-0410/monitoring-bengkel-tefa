import sqlite3

conn = sqlite3.connect('data/monitoring.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tables:", tables)

for t in tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    count = c.fetchone()[0]
    print(f"\n--- {t} ({count} rows) ---")
    c.execute(f"SELECT * FROM {t} LIMIT 5")
    cols = [d[0] for d in c.description]
    print("Columns:", cols)
    for row in c.fetchall():
        print(row)

conn.close()
