import sqlite3
import os
import sys


# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from shared.auth.auth_service import AuthService

# 使用临时数据库测试
TEST_DB = "./.mem0/test_auth.db"

def test_admin_flow():
    print("Starting Admin Flow Test...")
    
    # 清空全局 dependency_overrides，防止之前测试的 mock 污染
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    
    # 1. Setup - Directly patch the instances used by Routers
    import shared.auth.auth
    import core_graph.routers.admin
    
    # 强制将 Router 里的 Service 实例指向测试 DB
    test_db_path = os.path.abspath(TEST_DB)
    
    # Patch shared.auth.auth.auth_service (用于 login + get_current_user)
    shared.auth.auth.auth_service.db_path = test_db_path
    shared.auth.auth.auth_service._init_db()
    
    # Patch core_graph.routers.admin._auth_service (用于 admin API)
    core_graph.routers.admin._auth_service.db_path = test_db_path
    core_graph.routers.admin._auth_service._init_db()
    
    # 清理旧测试数据
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
        
    try:
        client = TestClient(app)
        
        # 2. Register Admin User (使用 shared.auth.auth.auth_service 确保和 login 用的是同一个实例的 DB)
        print("Creating Admin user...")
        shared.auth.auth.auth_service.create_user("admin_id", "admin", "admin123", role="admin")
        
        # 3. Register Normal User
        print("Creating Normal user...")
        shared.auth.auth.auth_service.create_user("user_id", "user", "user123", role="user")
        
        # Debug: 验证用户确实被创建了
        admin_user = shared.auth.auth.auth_service.get_user_by_id("admin_id")
        print(f"DEBUG Admin user: role={admin_user.get('role')}, id={admin_user.get('id')}")
        
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
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except:
                pass

if __name__ == "__main__":
    test_admin_flow()
