
import sqlite3
import json
import os

DB_PATH = "/Users/jinyijun/Documents/code/memory/.mem0/profile.db"

def clean_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT user_id, slots FROM user_profile")
        rows = cursor.fetchall()
        
        updated_count = 0
        for user_id, slots_json in rows:
            if not slots_json:
                continue
                
            slots = json.loads(slots_json)
            new_slots = {}
            has_changes = False
            
            for k, v in slots.items():
                # 过滤逻辑
                if v is None:
                    has_changes = True
                    continue
                if isinstance(v, str) and not v.strip():
                    has_changes = True
                    continue
                if isinstance(v, list):
                    # 过滤列表中的空串
                    new_list = [i for i in v if i and str(i).strip()]
                    if len(new_list) != len(v):
                        has_changes = True
                    if not new_list: # 如果整个列表都空了，也可以去掉
                        has_changes = True
                        continue
                    new_slots[k] = new_list
                else:
                    new_slots[k] = v
            
            if has_changes:
                print(f"Cleaning profile for user {user_id}...")
                cursor.execute(
                    "UPDATE user_profile SET slots = ? WHERE user_id = ?",
                    (json.dumps(new_slots, ensure_ascii=False), user_id)
                )
                updated_count += 1
                
        conn.commit()
        print(f"Done. Cleaned {updated_count} profiles.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    clean_db()
