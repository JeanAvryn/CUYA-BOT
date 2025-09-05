import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

try:
    c.execute("ALTER TABLE reports ADD COLUMN details TEXT;")
    print("✅ Column 'details' added successfully.")
except sqlite3.OperationalError as e:
    print("⚠️", e)  # Usually 'duplicate column' kung nadagdag mo na dati

conn.commit()
conn.close()
