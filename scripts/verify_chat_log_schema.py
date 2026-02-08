
import sqlite3
import os
import sys

# Ensure we can import from the project root
sys.path.append(os.path.abspath("/Users/jinyijun/Documents/code/memory"))

from services.chat_log_service import ChatLogService
from datetime import datetime

def verify():
    print("Verifying Chat Log Schema Changes...")
    
    # 1. Initialize Service (this should trigger _init_db and potential ALTER TABLE)
    service = ChatLogService()
    print("Service initialized.")
    
    # 2. Check Schema
    conn = sqlite3.connect(service.db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(chat_logs)")
    columns = [info[1] for info in cursor.fetchall()]
    conn.close()
    
    print(f"Current columns: {columns}")
    
    if "character_name" not in columns or "character_persona" not in columns:
        print("FAILED: New columns missing!")
        return
        
    print("SUCCESS: Schema updated successfully.")
    
    # 3. Test Logging
    user_id = "test_verifier_time"
    messages = [
        {"role": "user", "content": "Checking time"}
    ]
    character_name = "TimeBot"
    character_persona = "I care about precision."
    
    now_local = datetime.now()
    print(f"Current local time: {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("Logging message...")
    service.log_messages(
        user_id, 
        messages, 
        character_name=character_name, 
        character_persona=character_persona
    )
    
    # 4. Verify Data Retrieval
    conn = sqlite3.connect(service.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT created_at, character_name, character_persona FROM chat_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        db_time_str, db_name, db_persona = row
        print(f"DB Record: Time={db_time_str}, Name={db_name}")
        
        # Parse DB time
        db_time = datetime.strptime(db_time_str, "%Y-%m-%d %H:%M:%S")
        diff_seconds = abs((now_local - db_time).total_seconds())
        
        if diff_seconds < 5:
            print(f"SUCCESS: Time is accurate (diff={diff_seconds}s).")
        else:
            print(f"FAILED: Time discrepancy! diff={diff_seconds}s. DB={db_time_str}, Local={now_local.strftime('%Y-%m-%d %H:%M:%S')}")
            
        if db_name == character_name and db_persona == character_persona:
            print("SUCCESS: Character info verified.")
        else:
            print(f"FAILED: Character info mismatch. Got ({db_name}, {db_persona})")
    else:
        print("FAILED: No record found.")

if __name__ == "__main__":
    verify()
