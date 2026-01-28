
import sqlite3
import os
import json

db_path = "/Users/jinyijun/Documents/code/memory/.mem0/feedback.db"

def inspect_db():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("--- Table Info ---")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for t in tables:
            print(f"Table: {t['name']}")
            
        print("\n--- Recent Feedback Records ---")
        cursor.execute("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        
        if not rows:
            print("No records found in feedback table.")
        
        for row in rows:
            item = dict(row)
            print(json.dumps(item, indent=2, default=str))
            
        conn.close()
    except Exception as e:
        print(f"Error inspecting DB: {e}")

if __name__ == "__main__":
    inspect_db()
