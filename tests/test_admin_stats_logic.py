import sys
import os
import unittest
import sqlite3
import shutil
from datetime import datetime, timedelta

# Mock graphiti_core
import sys
from unittest.mock import MagicMock
sys.modules["graphiti_core"] = MagicMock()
sys.modules["graphiti_core.llm_client"] = MagicMock()
sys.modules["graphiti_core.llm_client.config"] = MagicMock()

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.auth_service import AuthService
from services.chat_log_service import ChatLogService

class TestAdminStats(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./.test_mem0"
        os.makedirs(self.test_dir, exist_ok=True)
        self.auth_db = os.path.join(self.test_dir, "auth.db")
        self.chat_db = os.path.join(self.test_dir, "chat_logs.db")
        
        self.auth_service = AuthService(db_path=self.auth_db)
        self.chat_service = ChatLogService(db_path=self.chat_db)
        
    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_auth_stats_since(self):
        # 1. Create users with different timestamps
        # Since AuthService.create_user uses CURRENT_TIMESTAMP, we need to manually hack it or just verify logic.
        # But wait, AuthService doesn't let us set created_at.
        # We'll manually insert into DB for testing purpose.
        
        conn = sqlite3.connect(self.auth_db)
        c = conn.cursor()
        
        # User 1: Created 2 days ago
        dt1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)", 
                  ("u1", "user1", "hash", dt1))
        
        # User 2: Created 1 hour ago
        dt2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)", 
                  ("u2", "user2", "hash", dt2))
        
        conn.commit()
        conn.close()
        
        # Test since 24h ago -> Should be 1 (User 2)
        since_24h = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        count_24h = self.auth_service.get_users_count_since(since_24h)
        self.assertEqual(count_24h, 1)
        
        # Test since 3 days ago -> Should be 2 (User 1, User 2)
        since_3d = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        count_3d = self.auth_service.get_users_count_since(since_3d)
        self.assertEqual(count_3d, 2)
        
        # Test since now -> Should be 0
        since_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count_now = self.auth_service.get_users_count_since(since_now)
        self.assertEqual(count_now, 0)

    def test_chat_stats_since(self):
        # 1. Log messages with different timestamps
        # User 1: 2 days ago
        dt1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        self.chat_service.log_message("u1", "user", "hi", created_at=dt1)
        
        # User 2: 1 hour ago
        dt2 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        self.chat_service.log_message("u2", "user", "hello", created_at=dt2)
        
        # User 2: 30 mins ago (Another message)
        dt3 = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        self.chat_service.log_message("u2", "user", "hello again", created_at=dt3)
        
        # Agent: 30 mins ago (Should not count in rounds)
        self.chat_service.log_message("u2", "assistant", "hi user", created_at=dt3)

        # Test since 24h ago
        # Active users: u2 (1)
        # rounds: u2 msg1 + u2 msg2 = 2
        since_24h = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        stats = self.chat_service.get_stats_since(since_24h)
        self.assertEqual(stats["active_users"], 1)
        self.assertEqual(stats["chat_rounds"], 2)
        
        # Test since 3 days ago
        # Active users: u1, u2 (2)
        # rounds: u1 msg1 + u2 msg1 + u2 msg2 = 3
        since_3d = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        stats = self.chat_service.get_stats_since(since_3d)
        self.assertEqual(stats["active_users"], 2)
        self.assertEqual(stats["chat_rounds"], 3)

if __name__ == '__main__':
    unittest.main()
