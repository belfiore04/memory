import sys
import os
sys.path.append(os.getcwd())

from services.chat_log_service import ChatLogService
from datetime import datetime

def check_stats():
    service = ChatLogService()
    print("Checking stats...")
    stats = service.get_stats()
    print(f"Stats: {stats}")
    
    # Check manual query
    import sqlite3
    conn = sqlite3.connect(service.db_path)
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Querying for date: {today_str}")
    
    cursor.execute("SELECT created_at FROM chat_logs ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    print(f"Recent logs: {rows}")
    
    conn.close()

if __name__ == "__main__":
    check_stats()
