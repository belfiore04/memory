import sqlite3
import os

db_path = os.path.abspath(".mem0/focus.db")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Recent Whisper Suggestions ---")
    cursor.execute("SELECT id, user_id, suggestion, is_consumed, created_at FROM whisper_suggestions ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    print("\n--- Active User Focus ---")
    cursor.execute("SELECT id, user_id, content, status FROM user_focus WHERE status = 'active'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
