import os
import sqlite3
import json
import asyncio
import logging
from datetime import datetime
from services.auth_service import AuthService
from services.memory_service import MemoryService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    auth_service = AuthService()
    memory_service = MemoryService()
    
    # 1. 扫描旧用户
    chat_log_db = "./.mem0/chat_logs.db"
    conn = sqlite3.connect(chat_log_db)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM chat_logs")
    old_user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    logger.info(f"发现旧用户: {old_user_ids}")
    
    # 2. 初始化账号
    # 我们假设 '1' 是 Primary User，如果不存在则使用发现的第一个，或者默认创建一个管理员
    primary_user_id = '1' if '1' in old_user_ids else (old_user_ids[0] if old_user_ids else 'admin')
    
    for uid in old_user_ids:
        if not auth_service.get_user_by_id(uid):
            username = f"user_{uid}"
            password = "password" # 默认密码
            auth_service.create_user(uid, username, password)
            logger.info(f"为旧用户 {uid} 创建了新账号: {username}")
            
    # 3. 迁移图数据 (Legacy -> Primary User)
    logger.info(f"开始迁移图数据到主账号: {primary_user_id}")
    
    try:
        # 获取原有 default_db 的所有数据
        # 由于我们重构了 MemoryService，我们需要一个直接连接 default_db 的方式
        base_driver = memory_service.base_driver
        default_graph = base_driver.client.select_graph("default_db")
        
        # 查询所有节点和边 (简单克隆逻辑)
        # 注意：Graphiti 内部结构复杂，最简单的方法是全量 Cypher 迁移
        
        # 获取所有节点
        node_query = "MATCH (n) RETURN labels(n) as labels, properties(n) as props, id(n) as old_id"
        node_records = await base_driver.execute_query(node_query) # 这里 execute_query 默认用的是 _database 也就是 default_db
        # 如果 MemoryService 里的 base_driver 默认就是 default_db，则直接用
        
        # 由于我们要跨 Graph 迁移，我们需要在 target 库里重建
        target_graph_name = f"user_{primary_user_id}"
        target_driver = base_driver.clone(database=target_graph_name)
        
        logger.info(f"正在拷贝数据到 {target_graph_name}...")
        
        # 简单策略：直接在目标库执行 MATCH (n) DETACH DELETE n 确保存储空间干净 (可选)
        await target_driver.execute_query("MATCH (n) DETACH DELETE n")
        
        # 1. 迁移节点
        # 这里的 node_records 是 (records, header, _)
        records = node_records[0]
        id_map = {} # old_id -> new_id
        
        for r in records:
            labels = ":".join(r['labels'])
            props = r['props']
            # 这里需要小心处理参数
            create_query = f"CREATE (n:{labels}) SET n = $props RETURN id(n) as new_id"
            res, _, _ = await target_driver.execute_query(create_query, props=props)
            id_map[r['old_id']] = res[0]['new_id']
            
        # 2. 迁移关系
        rel_query = "MATCH (n)-[r]->(m) RETURN id(n) as start_id, type(r) as rel_type, properties(r) as props, id(m) as end_id"
        rel_records, _, _ = await base_driver.execute_query(rel_query)
        
        for r in rel_records:
            start_new = id_map.get(r['start_id'])
            end_new = id_map.get(r['end_id'])
            if start_new is not None and end_new is not None:
                rel_type = r['rel_type']
                create_rel = f"""
                MATCH (a), (b)
                WHERE id(a) = {start_new} AND id(b) = {end_new}
                CREATE (a)-[r:{rel_type}]->(b)
                SET r = $props
                """
                await target_driver.execute_query(create_rel, props=r['props'])
        
        logger.info("图数据迁移完成！")
        
    except Exception as e:
        logger.error(f"图数据迁移失败: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate())
