import os
import unittest
import shutil
import tempfile
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

# 导入服务
# 注意：这里假设运行目录是项目根目录，或者 PYTHONPATH 包含项目根目录
from services.focus_service import FocusService

class TestFocusTime(unittest.TestCase):
    def setUp(self):
        # 1. 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        
        # 2. 切换当前工作目录到临时目录，以便 FocusService 在这里创建 .mem0
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # 3. 初始化服务
        self.service = FocusService()

    def tearDown(self):
        # 还原目录并清理
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_expiration_logic(self):
        user_id = "test_user_time"
        today = datetime.now().date()
        
        print(f"\n[Test] Today is {today}")
        
        # Case 1: 已过期 (两天前的事项)
        # Expiration rule: today > expected + 1 day
        # active until: expected + 1 day
        past_date = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        self.service.add_focus(user_id, "已过期事项", expected_date=past_date)
        
        # Case 2: 刚过期? (昨天的事项)
        # expected: yesterday. active until: yesterday + 1 = today. 
        # today > today is False. So still active today.
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        self.service.add_focus(user_id, "昨天事项(缓冲期)", expected_date=yesterday)
        
        # Case 3: 进行中 (今天)
        today_str = today.strftime("%Y-%m-%d")
        self.service.add_focus(user_id, "今日事项", expected_date=today_str)
        
        # Case 4: 未来 (明天)
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        self.service.add_focus(user_id, "明日事项", expected_date=tomorrow_str)
        
        # Case 5: 无明确日期 (默认 TTL)
        self.service.add_focus(user_id, "普通事项")
        
        # Case 6: 模拟 TTL 过期 (手动修改 created_at)
        self.service.add_focus(user_id, "TTL过期事项")
        # 直接改库模拟 created_at 为 20 天前
        import sqlite3
        conn = sqlite3.connect(self.service.db_path)
        cursor = conn.cursor()
        old_date = datetime.now() - timedelta(days=20)
        cursor.execute("UPDATE user_focus SET created_at = ? WHERE content = ?", (old_date, "TTL过期事项"))
        conn.commit()
        conn.close()
        
        # --- 验证 ---
        active_list = self.service.get_active_focus_with_time(user_id)
        contents = [f["content"] for f in active_list]
        
        print("\n[Result] Active items:")
        for item in active_list:
            print(item)
            
        # Assertions
        self.assertNotIn("已过期事项", contents, "过期事项不应出现")
        self.assertNotIn("TTL过期事项", contents, "TTL过期事项不应出现")
        
        self.assertIn("昨天事项(缓冲期)", contents, "昨天的事项今天应该还在(缓冲期)")
        self.assertIn("今日事项", contents)
        self.assertIn("明日事项", contents)
        self.assertIn("普通事项", contents)

    def test_refresh_logic(self):
        user_id = "test_user_refresh"
        
        # 1. 添加一个普通事项
        self.service.add_focus(user_id, "我要健身")
        
        # 获取 created_at, updated_at
        conn = sqlite3.connect(self.service.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at, expected_date FROM user_focus WHERE content = ?", ("我要健身",))
        row1 = cursor.fetchone()
        conn.close()
        
        # 2. 模拟时间流逝后再次添加 (无日期)
        # 这里只是模拟 API 调用，实际 created_at 不变，updated_at 更新
        self.service.add_focus(user_id, "我要健身")
        
        conn = sqlite3.connect(self.service.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at, expected_date FROM user_focus WHERE content = ?", ("我要健身",))
        row2 = cursor.fetchone()
        conn.close()
        
        self.assertEqual(row1[0], row2[0], "created_at 应该不变")
        self.assertNotEqual(row1[1], row2[1], "updated_at 应该更新")
        
        # 3. 再次添加并带上 expected_date
        self.service.add_focus(user_id, "我要健身", expected_date="2026-02-01")
        
        conn = sqlite3.connect(self.service.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT expected_date FROM user_focus WHERE content = ?", ("我要健身",))
        row3 = cursor.fetchone()
        conn.close()
        
        self.assertEqual(row3[0], "2026-02-01", "expected_date 应该更新")

    def test_cooling_down_logic(self):
        user_id = "test_user_cool"
        self.service.add_focus(user_id, "冷却测试事项")
        
        # 1. 初始状态：应该可见
        active = self.service.get_active_focus_with_time(user_id)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["content"], "冷却测试事项")
        focus_id = active[0]["id"]
        
        # 2. 标记为已注入
        self.service.mark_focus_injected(focus_id)
        
        # 3. 立即查看：应该不可见 (处于12h冷却中)
        active_now = self.service.get_active_focus_with_time(user_id)
        self.assertEqual(len(active_now), 0, "注入后应该进入冷却期不可见")
        
        # 4. 模拟过了 13 小时
        import sqlite3
        conn = sqlite3.connect(self.service.db_path)
        cursor = conn.cursor()
        old_time = datetime.now() - timedelta(hours=13)
        cursor.execute("UPDATE user_focus SET last_injected_at = ? WHERE id = ?", (old_time, focus_id))
        conn.commit()
        conn.close()
        
        # 5. 再次查看：应该可见
        active_later = self.service.get_active_focus_with_time(user_id)
        self.assertEqual(len(active_later), 1, "冷却期过后应该恢复可见")
        self.assertEqual(active_later[0]["content"], "冷却测试事项")

if __name__ == "__main__":
    import sqlite3 
    unittest.main()
