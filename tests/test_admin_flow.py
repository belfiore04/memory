import os
import sys
import sqlite3

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from services.auth_service import AuthService

# 使用临时数据库测试
TEST_DB = "./.mem0/test_auth.db"

def test_admin_flow():
    print("Starting Admin Flow Test...")
    
    # 1. Setup - Directly patch the instances used by Routers
    import routers.auth
    import routers.admin
    
    # 强制将 Router 里的 Service 实例指向测试 DB
    test_db_path = os.path.abspath(TEST_DB)
    
    # Patch routers.auth.auth_service
    routers.auth.auth_service.db_path = test_db_path
    routers.auth.auth_service._init_db() # 重新初始化以确保表存在
    
    # Patch routers.admin._auth_service
    routers.admin._auth_service.db_path = test_db_path
    
    # 我们自己测试脚本里用的 helper service
    auth_service = AuthService(db_path=TEST_DB)
    
    # 清理旧测试数据
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
        
    try:
        client = TestClient(app)
        
        # 2. Register Admin User
        print("Creating Admin user...")
        auth_service.create_user("admin_id", "admin", "admin123", role="admin")
        
        # 3. Register Normal User
        print("Creating Normal user...")
        auth_service.create_user("user_id", "user", "user123", role="user")
        
        # 4. Test Login as Admin
        print("Logging in as Admin...")
        res = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        admin_token = res.json()["access_token"]
        
        # 5. Test Login as User
        print("Logging in as User...")
        res = client.post("/auth/login", data={"username": "user", "password": "user123"})
        assert res.status_code == 200, f"User login failed: {res.text}"
        user_token = res.json()["access_token"]
        
        # 6. Test Admin Access (Should Succeed)
        print("Testing Admin Access...")
        res = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Admin access failed: {res.text}"
        users = res.json()
        assert len(users) == 2, f"Expected 2 users, got {len(users)}"
        
        # 7. Test User Access to Admin API (Should Fail)
        print("Testing User Access Restriction...")
        res = client.get("/admin/users", headers={"Authorization": f"Bearer {user_token}"})
        assert res.status_code == 403, f"User access should be forbidden, got {res.status_code}"
        
        # 8. Test Ban User
        print("Testing Ban User...")
        res = client.put("/admin/users/user_id", 
                         json={"is_active": False}, 
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, f"Ban user failed: {res.text}"
        
        # 9. Test Banned User Login (Should Fail)
        print("Testing Banned User Login...")
        res = client.post("/auth/login", data={"username": "user", "password": "user123"})
        assert res.status_code == 403, f"Banned user should not login, got {res.status_code}"
        assert res.json()["detail"] == "Account is banned"
        
        print("✅ All Admin Flow verified successfully!")
        
    finally:
        # 10. Cleanup
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except:
                pass

if __name__ == "__main__":
    test_admin_flow()
