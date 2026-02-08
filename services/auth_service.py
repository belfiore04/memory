import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-it-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

class AuthService:
    def __init__(self, db_path: str = "./.mem0/auth.db"):
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 创建基本表结构 (如果不存在)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 检查并添加 role 字段
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "role" not in columns:
            logger.info("Migrating database: Adding 'role' column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            # 迁移策略：所有现有用户升级为 admin
            cursor.execute("UPDATE users SET role = 'admin'")
            
        # 3. 检查并添加 is_active 字段
        if "is_active" not in columns:
            logger.info("Migrating database: Adding 'is_active' column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            
        # 4. 检查并添加 ai_name 和 persona 字段
        if "ai_name" not in columns:
            logger.info("Migrating database: Adding 'ai_name' column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN ai_name TEXT")
            
        if "persona" not in columns:
            logger.info("Migrating database: Adding 'persona' column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN persona TEXT")

        conn.commit()
        conn.close()

    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_all_users(self) -> list[Dict[str, Any]]:
        """获取所有用户列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, created_at, role, is_active FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def create_user(self, user_id: str, username: str, password: str, role: str = "user") -> bool:
        try:
            hashed_password = self.get_password_hash(password)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (id, username, password_hash, role, is_active) VALUES (?, ?, ?, ?, 1)",
                (user_id, username, hashed_password, role)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            print(f"CRITICAL ERROR creating user: {e}") # Force print to stdout
            import traceback
            traceback.print_exc()
            return False

    def update_user_role(self, user_id: str, role: str) -> bool:
        """更新用户角色"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新用户角色失败: {e}")
            return False

    def update_user_status(self, user_id: str, is_active: bool) -> bool:
        """更新用户状态"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            val = 1 if is_active else 0
            cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (val, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            return False

    def update_user_settings(self, user_id: str, ai_name: Optional[str] = None, persona: Optional[str] = None) -> bool:
        """更新用户 AI 设定"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 动态构建 SQL
            updates = []
            params = []
            if ai_name is not None:
                updates.append("ai_name = ?")
                params.append(ai_name)
            if persona is not None:
                updates.append("persona = ?")
                params.append(persona)
                
            if not updates:
                conn.close()
                return True
                
            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            
            cursor.execute(sql, tuple(params))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新用户 AI 设定失败: {e}")
            return False

    def get_users_count_since(self, since_at: str) -> int:
        """获取指定时间之后的新增用户数"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (since_at,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"获取新增用户数失败: {e}")
            return 0
