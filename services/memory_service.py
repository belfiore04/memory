#!/usr/bin/env python3
"""
记忆服务模块
提供基于 Graphiti 的智能记忆管理，支持时序知识图谱
"""

import os
import json
import logging
import asyncio
from typing import Optional, List, Dict, Literal, Any
from datetime import datetime, timezone
import time
from services.llm_logger import log_llm_call, configure_graphiti_logging
from langfuse import observe, get_client
from dotenv import load_dotenv
from openai import OpenAI
from agents.memory_decision_agent import MemoryDecisionAgent

# Graphiti imports
from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.nodes import EpisodeType

# 配置日志系统
def setup_logging():
    """配置日志系统"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_filename = os.path.join(log_dir, f"memory_service_{datetime.now().strftime('%Y%m%d')}.log")
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8')
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

# 操作类型定义
ActionType = Literal["STORE", "RETRIEVE", "NONE"]


class MemoryService:
    """记忆服务类 - 提供基于 Graphiti 的智能记忆管理"""
    
    def __init__(self):
        """初始化记忆服务"""
        logger.info("=" * 80)
        logger.info("初始化 Multi-Tenant Graphiti 记忆服务")
        logger.info("=" * 80)
        
        # 加载环境变量
        load_dotenv()
        
        # 初始化 OpenAI 客户端（用于 LLM 判断）
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.dashscope_api_key:
            raise ValueError("未找到 DASHSCOPE_API_KEY 环境变量")
        
        self.dashscope_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAI(api_key=self.dashscope_api_key, base_url=self.dashscope_base_url)
        self.ability_model = os.getenv("ABILITY_MODEL", "qwen-max")
        self.speed_model = os.getenv("SPEED_MODEL", "qwen-flash")
        
        # 初始化决策 Agent
        self.decision_agent = MemoryDecisionAgent()

        # Episode 开关
        self.include_episodes = os.getenv("INCLUDE_EPISODES", "true").lower() == "true"

        # 1. 共享 LLM Client 配置
        self.llm_config = LLMConfig(
            api_key=self.dashscope_api_key,
            model=self.ability_model,
            small_model=self.speed_model,
            base_url=self.dashscope_base_url,
        )
        self.llm_client = OpenAIGenericClient(config=self.llm_config)
        
        # 2. 共享 Embedder 配置
        self.embedder = OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=self.dashscope_api_key,
                embedding_model="text-embedding-v4",
                embedding_dim=1024,
                base_url=self.dashscope_base_url,
            )
        )

        # 3. 基础 FalkorDB Driver (用于 Clone)
        falkor_host = os.getenv("FALKORDB_HOST", "localhost")
        falkor_port = int(os.getenv("FALKORDB_PORT", 6380))
        logger.info(f"Connecting to FalkorDB at {falkor_host}:{falkor_port} (Env: {os.getenv('FALKORDB_HOST')})")
        self.base_driver = FalkorDriver(host=falkor_host, port=falkor_port)
        
        # 4. 实例缓存 {user_id: GraphitiInstance}
        self.user_instances: Dict[str, Graphiti] = {}
        logger.info(f"✓ Multi-Tenant 基础组件初始化完毕 (FalkorDB @ {falkor_host}:{falkor_port})")

    def _get_graph_for_user(self, user_id: str) -> Graphiti:
        """为特定用户获取或创建 Graphiti 实例 (Per-User Graph)"""
        if user_id in self.user_instances:
            return self.user_instances[user_id]
        
        # 使用数据库名隔离: user_{id}
        # 这里的 id 可能是 UUID 或 1, 我们统一加上前缀避免非法 key
        graph_db_name = f"user_{user_id}"
        
        user_driver = self.base_driver.clone(database=graph_db_name)
        
        instance = Graphiti(
            graph_driver=user_driver,
            llm_client=self.llm_client,
            embedder=self.embedder,
            cross_encoder=OpenAIRerankerClient(client=self.llm_client, config=self.llm_config),
        )
        
        self.user_instances[user_id] = instance
        logger.info(f"[MemoryService] 为用户 {user_id} 创建了独立图谱实例: {graph_db_name}")
        return instance
    
    async def retrieve(self, user_id: str, query: str) -> Dict:
        """
        判断是否需要检索记忆，并返回相关记忆 (Async)
        """
        logger.info(f"[Retrieve] user_id={user_id}, query={query[:50]}...")

        with get_client().start_as_current_span(name="判断是否要检索记忆") as span:
            # 1. 使用 LLM 判断是否需要检索
            should_retrieve, reason = await self._should_retrieve(query)
            logger.info(f"[Retrieve] should_retrieve={should_retrieve}, reason={reason}")

            # 2. 如果需要检索，执行检索
            memories = []
            episodes = []
            if should_retrieve:
                search_result = await self.search(user_id, query)
                memories = search_result.get("memories", [])
                episodes = search_result.get("episodes", [])

            return {
                "should_retrieve": should_retrieve,
                "reason": reason,
                "memories": memories,
                "episodes": episodes
            }
    
    async def _should_retrieve(self, query: str) -> tuple[bool, str]:
        """
        使用 MemoryDecisionAgent 判断是否需要检索记忆
        """
        return self.decision_agent.should_retrieve(query)
    
    @observe(name="在graphiti中添加episode")
    async def add_memory_item(self, user_id: str, content: str, type: str = "fact") -> Dict:
        """
        直接添加一条记忆项
        """
        logger.info(f"[AddMemoryItem] user_id={user_id}, content={content[:30]}..., type={type}")
        
        graphiti = self._get_graph_for_user(user_id)
            
        try:
            current_time = datetime.now(timezone.utc)
            await graphiti.add_episode(
                name=f"api_add_{int(current_time.timestamp())}",
                episode_body=content,
                source=EpisodeType.text,
                source_description=f"direct_add_{type}",
                reference_time=current_time
            )
            
            logger.info(f"[AddMemoryItem] 添加成功")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"[AddMemoryItem] 添加失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def add_memory_direct(self, user_id: str, content: str, type: str = "conversation_turn", reason: str = "") -> Dict:
        """
        直接添加记忆 (Graphiti 方式)
        """
        return await self.add_memory_item(user_id, content, type)
    
    @observe(name="Memory Smart Store")
    async def smart_store(self, user_id: str, messages: List[Dict[str, str]]) -> Dict:
        """
        智能存储：先判断是否需要存储，再执行存储
        """
        logger.info(f"[SmartStore] user_id={user_id}, messages_count={len(messages)}")
        
        # 1. 使用 LLM 判断是否需要存储
        should_store, reason = await self._should_store(messages)
        logger.info(f"[SmartStore] should_store={should_store}, reason={reason}")
        
        # 2. 如果需要存储，执行存储
        if should_store:
            store_result = await self.store(user_id, messages)
            return {
                "should_store": True,
                "reason": reason,
                "success": store_result.get("success", False),
                "stored_count": store_result.get("stored_count", 0),
                "stored_memories": store_result.get("stored_memories", [])
            }
        else:
            return {
                "should_store": False,
                "reason": reason,
                "success": True,
                "stored_count": 0,
                "stored_memories": []
            }
    
    async def _should_store(self, messages: List[Dict[str, str]]) -> tuple[bool, str]:
        """
        使用 MemoryDecisionAgent 判断是否需要存储记忆
        """
        return self.decision_agent.should_store(messages)

    async def store(self, user_id: str, messages: List[Dict[str, str]]) -> Dict:
        """
        存储对话到 Graphiti (添加为 Episode)
        """
        graphiti = self._get_graph_for_user(user_id)
        
        try:
            # 将对话格式化为文本
            conversation_text = ""
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                conversation_text += f"{role}: {content}\\n"
            
            current_time = datetime.now(timezone.utc)
            
            # Graphiti 将自动处理实体和关系提取
            await graphiti.add_episode(
                name=f"chat_{int(current_time.timestamp())}",
                episode_body=conversation_text,
                source=EpisodeType.text,
                source_description="chat conversation",
                reference_time=current_time
            )
            
            logger.info(f"[Store] 存储成功 (user_id={user_id})")
            return {"success": True, "stored_count": 1, "stored_memories": [{"content": "Processing in background"}]}
            
        except Exception as e:
            logger.error(f"[Store] 存储失败: {str(e)}")
            return {"success": False, "error": str(e)}
            
    @observe(name="在graphiti中检索")
    async def search(self, user_id: str, query: str, limit: int = 5) -> Dict:
        """
        搜索相关记忆，包含时序信息
        返回: {"memories": [...], "episodes": [...]}
        """
        graphiti = self._get_graph_for_user(user_id)

        try:
            results = await graphiti.search(query)
            # Graphiti results object structure:
            # fact, valid_at, invalid_at, created_at, etc.

            memories = []
            edge_uuids = []
            for r in results[:limit]:
                valid_at = getattr(r, 'valid_at', None)
                invalid_at = getattr(r, 'invalid_at', None)
                created_at = getattr(r, 'created_at', None)

                # 转换时间为 ISO 字符串
                valid_at_str = valid_at.isoformat() if valid_at else None
                invalid_at_str = invalid_at.isoformat() if invalid_at else None
                created_at_str = created_at.isoformat() if created_at else None

                edge_uuid = getattr(r, 'uuid', '')
                if edge_uuid:
                    edge_uuids.append(edge_uuid)

                memories.append({
                    "id": edge_uuid,
                    "content": r.fact,
                    "score": getattr(r, 'score', 0),
                    "valid_at": valid_at_str,
                    "invalid_at": invalid_at_str,
                    "created_at": created_at_str
                })

            # 如果开关关闭，跳过 Episodic 查询
            if not self.include_episodes or not edge_uuids:
                return {"memories": memories, "episodes": []}

            # 反查这些 Edge 所属的 Episodic
            try:
                driver = graphiti.driver
                query_episodes = """
                MATCH (e:Episodic)-[:MENTIONS]->(n:Entity)-[r]->(m:Entity)
                WHERE r.uuid IN $uuids
                RETURN DISTINCT e.content as content, e.source_description as type, e.created_at as created_at
                ORDER BY e.created_at DESC
                """
                episode_records, _, _ = await driver.execute_query(
                    query_episodes, {"uuids": edge_uuids}
                )

                episodes = []
                for record in episode_records:
                    created_at = record.get("created_at")
                    if hasattr(created_at, 'isoformat'):
                        created_at = created_at.isoformat()
                    episodes.append({
                        "content": record.get("content", ""),
                        "type": record.get("type", ""),
                        "created_at": created_at
                    })

                logger.info(f"[Search] 找到 {len(memories)} 条 Edge，{len(episodes)} 条 Episode")
                return {"memories": memories, "episodes": episodes}

            except Exception as ep_err:
                logger.warning(f"[Search] Episode 反查失败（非致命）: {str(ep_err)}")
                return {"memories": memories, "episodes": []}

        except Exception as e:
            logger.error(f"[Search] 搜索失败: {str(e)}")
            return {"memories": [], "episodes": []}
            
    async def get_all(self, user_id: str) -> Dict:
        """
        获取所有记忆，并按关系类型分组返回历史变化
        """
        graphiti = self._get_graph_for_user(user_id)

        try:
            # 使用 Graphiti 的 driver 直接执行 Cypher 查询
            driver = graphiti.driver
            
            # 查询语句：获取所有 EntityEdge 及其属性
            # 注意：Graphiti 默认使用 Neo4jDriver 接口，即使底层是 FalkorDB
            # execute_query 是 async 方法
            # 过滤掉 MENTIONS 关系（这是 Episode 到 Entity 的元数据关系，不是真正的记忆）
            query = """
            MATCH (n)-[r]->(m)
            WHERE type(r) <> 'MENTIONS'
            RETURN n.name AS subject, type(r) AS relation, m.name AS object, r.fact AS fact, r.valid_at AS valid_at, r.invalid_at AS invalid_at, r.created_at AS created_at
            """
            
            # execute_query returns (records, summary, keys)
            records, _, _ = await driver.execute_query(query)
            
            memories = []
            grouped_history = {} 

            for record in records:
                # record 类似于 dict (Neo4j driver behavior)
                subject = record['subject']
                relation = record['relation']
                object_ = record['object']
                fact = record['fact']
                valid_at = record['valid_at']
                invalid_at = record['invalid_at']
                created_at = record['created_at']

                # Graphiti 返回的时间可能是 datetime 对象或字符串，这里根据实际情况处理
                # 如果是 datetime，转换为 ISO string
                if hasattr(valid_at, 'isoformat'):
                    valid_at = valid_at.isoformat()
                if hasattr(invalid_at, 'isoformat'):
                    invalid_at = invalid_at.isoformat()
                if hasattr(created_at, 'isoformat'):
                    created_at = created_at.isoformat()

                is_current = invalid_at is None
                
                item = {
                    "subject": subject,
                    "relation": relation,
                    "object": object_,
                    "content": fact, 
                    "fact": fact,
                    "valid_at": valid_at,
                    "invalid_at": invalid_at,
                    "created_at": created_at,
                    "is_current": is_current
                }
                memories.append(item)
                
                # 分组逻辑
                if relation not in grouped_history:
                    grouped_history[relation] = {
                        "label": relation, # 后端直接返回英文 key
                        "history": []
                    }
                grouped_history[relation]["history"].append(item)

            # 对每组历史按 valid_at 排序
            for rel in grouped_history:
                grouped_history[rel]["history"].sort(key=lambda x: x.get("valid_at") or "")

            # 查询 Episodic 节点（完整原始记忆）
            episodes = []
            if self.include_episodes:
                try:
                    query_episodes = """
                    MATCH (e:Episodic)
                    RETURN e.name as name, e.content as content, e.source_description as type,
                           e.created_at as created_at
                    ORDER BY e.created_at DESC
                    """
                    episode_records, _, _ = await driver.execute_query(query_episodes)

                    for record in episode_records:
                        created_at = record.get("created_at")
                        if hasattr(created_at, 'isoformat'):
                            created_at = created_at.isoformat()
                        episodes.append({
                            "name": record.get("name", ""),
                            "content": record.get("content", ""),
                            "type": record.get("type", ""),
                            "created_at": created_at
                        })
                    logger.info(f"[Get All] 找到 {len(episodes)} 条 Episodic 记忆")
                except Exception as ep_err:
                    logger.warning(f"[Get All] Episodic 查询失败（非致命）: {str(ep_err)}")

            return {
                "memories": memories,
                "episodes": episodes,
                "count": len(memories) + len(episodes)
            }

        except Exception as e:
            logger.error(f"[Get All] 查询失败: {str(e)}")
            return {"memories": [], "episodes": [], "count": 0, "error": str(e)}

    async def clear(self, user_id: str) -> Dict:
        """
        清空所有记忆 (直接物理删除该用户的图谱)
        """
        try:
            graph_db_name = f"user_{user_id}"
            # FalkorDB API 本身没有直接通过 python 驱动删除库的方法，
            # 最干净的方法是执行 MATCH (n) DETACH DELETE n 或者通过底层连接删除。
            # 这里由于已经有了 user_driver.clone，我们直接在对应的图上执行清空。
            
            graphiti = self._get_graph_for_user(user_id)
            driver = graphiti.driver
            
            # 删除所有节点和关系
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            
            logger.info(f"已清空用户 {user_id} 的图数据库 ({graph_db_name})")
            return {"success": True, "cleared_count": -1, "message": f"Graph for user {user_id} cleared"}  
            
        except Exception as e:
            logger.error(f"[Clear] 清除失败: {str(e)}")
            return {"success": False, "cleared_count": 0, "error": str(e)}

    async def pollute_memory(self, user_id: str) -> Dict:
        """
        [DEBUG] 污染记忆库：插入50条无关数据
        """
        noise_data = [
            "我非常讨厌吃香菜，一点都不能碰。",
            "我小时候的梦想是成为一名宇航员，探索宇宙。",
            "我最近开始学习拉大提琴，虽然很难但很有趣。",
            "其实我有幽闭恐惧症，不敢坐狭小的电梯。",
            "我最喜欢的电影是诺兰的《星际穿越》，看了很多遍。",
            "每个周末只要天气好，我都会去公园跑步五公里。",
            "我不喝咖啡，每天早上只喝一杯热红茶。",
            "家里养了一只温顺的金毛犬，名字叫'大黄'。",
            "我对花粉严重过敏，春天必须戴口罩。",
            "去年夏天我和朋友去冰岛自驾游，看到了极光。"
        ]
        
        if len(noise_data) > 10:
            noise_data = noise_data[:10]
        
        logger.info(f"[Pollute] 开始向用户 {user_id} 注入 {len(noise_data)} 条噪声数据")
        count = 0
        for fact in noise_data:
            try:
                # 标记为 'noise' 类型以便区分（如果支持自定义type的话，或者就混入 fact）
                await self.add_memory_item(user_id, fact, type="noise_fact")
                count += 1
            except Exception as e:
                logger.error(f"[Pollute] 注入失败: {fact[:10]}... {str(e)}")
        
        logger.info(f"[Pollute] 注入完成，共 {count} 条")
        return {"success": True, "polluted_count": count}
