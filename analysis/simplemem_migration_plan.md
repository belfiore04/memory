# SimpleMem 迁移计划

## 概述

本文档详细列出将项目的记忆系统从 **Graphiti (`graphiti-core`) + FalkorDB** 迁移到 **SimpleMem** 框架所需的所有步骤、需要改动的文件、需要用户确认的决策点，以及技术上无法迁移需要重新考虑的功能。

> [!WARNING]
> 此迁移属于 **架构级重构**，预计工作量 **3-5 天**。强烈建议在独立分支进行，并准备回滚方案。

---

## 第一阶段：依赖与环境准备

### 步骤 1.1：安装 SimpleMem

```bash
pip install simplemem
# 或带 GPU 支持
pip install simplemem[gpu]
```

### 步骤 1.2：更新 `requirements.txt`

```diff
- graphiti-core[falkordb]
+ simplemem
```

### 步骤 1.3：配置环境变量

在 `.env` 中新增：

```dotenv
# SimpleMem 配置
OPENAI_API_KEY=<your-openai-or-dashscope-key>
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # 如使用 Qwen
SIMPLEMEM_MODEL=qwen-max                                            # 可选覆盖
SIMPLEMEM_EMBEDDING_MODEL=text-embedding-v4                         # 可选覆盖
```

> [!IMPORTANT]
> **需要用户确认**: SimpleMem 默认使用 OpenAI API。你目前使用 DashScope (Qwen) 作为后端。请确认 SimpleMem 的 `OPENAI_BASE_URL` 设置是否能与 DashScope 正常工作。

---

## 第二阶段：核心服务重写

### 步骤 2.1：重写 `services/memory_service.py`

这是最重要的改动。需要将整个文件从使用 Graphiti 改为 SimpleMem。

#### 当前架构 (Graphiti)

```python
from graphiti_core import Graphiti
# ...
class MemoryService:
    def __init__(self):
        self.user_instances: Dict[str, Graphiti] = {}  # 多租户图谱缓存
    
    def _get_graph_for_user(self, user_id: str) -> Graphiti:
        # 为每个用户创建独立的 FalkorDB 实例
        ...
    
    async def add_memory_item(self, user_id, content, type):
        await graphiti.add_episode(...)
    
    async def search(self, user_id, query):
        results = await graphiti.search(query)
        # 返回 Edge 和 Episode
```

#### 新架构 (SimpleMem)

```python
from simplemem import SimpleMemSystem

class MemoryService:
    def __init__(self):
        # 多租户：为每个用户创建独立的 SimpleMemSystem 实例
        self.user_systems: Dict[str, SimpleMemSystem] = {}
    
    def _get_system_for_user(self, user_id: str) -> SimpleMemSystem:
        if user_id not in self.user_systems:
            # ⚠️ 需要解决持久化问题 (见下方)
            self.user_systems[user_id] = SimpleMemSystem(
                clear_db=False,  # 不清空已有数据
                # 可能需要指定 db_path=f"./data/{user_id}/" 之类的路径
            )
        return self.user_systems[user_id]
    
    async def add_memory_item(self, user_id, content, type):
        system = self._get_system_for_user(user_id)
        # SimpleMem 使用 add_dialogue 而非 add_episode
        system.add_dialogue(
            speaker="user",          # 或根据 type 判断
            content=content,
            timestamp=datetime.now().isoformat()
        )
        system.finalize()  # ⚠️ 每次添加后需要 finalize
    
    async def search(self, user_id, query):
        system = self._get_system_for_user(user_id)
        answer = system.ask(query)  # 返回字符串答案，不是 Edge 列表
        return {"memories": [{"content": answer}], "episodes": []}
```

> [!CAUTION]
> **API 结构差异巨大**:
>
> - Graphiti 的 `search()` 返回 **Edge 列表** (fact, score, valid_at 等)
> - SimpleMem 的 `ask()` 返回 **单个字符串答案**
>
> 这意味着前端的 `memories` 列表渲染逻辑需要适配。

### 步骤 2.2：多租户隔离问题 (需要用户决策)

> [!IMPORTANT]
> **需要用户确认**:
> SimpleMem 默认将数据存储在本地 SQLite 中，**不支持原生的多用户数据库隔离**。你需要选择以下方案之一：
>
> 1. **文件路径隔离**: 为每个用户指定不同的 `db_path`
>
>    ```python
>    SimpleMemSystem(db_path=f"./simplemem_data/user_{user_id}/")
>    ```
>
>    - 优点: 简单
>    - 缺点: 目前 SimpleMem 0.1.0 API 可能不支持自定义路径
>
> 2. **完全不隔离**: 所有用户共享一个内存库
>    - 优点: 代码简单
>    - 缺点: 隐私风险，用户 A 可能检索到用户 B 的记忆
>
> 3. **放弃迁移**: 继续使用 Graphiti + FalkorDB

---

## 第三阶段：API 路由层适配

### 步骤 3.1：修改 `routers/memory.py`

| 原接口 | 改动 |
|--------|------|
| `POST /{user_id}/retrieve` | 返回结构变化：从 `memories: [{content, score, valid_at, ...}]` 变为 `memories: [{content}]` |
| `POST /{user_id}/store` | 内部调用 `add_dialogue` + `finalize` 而非 `add_episode` |
| `GET /{user_id}` (列出所有) | **无法迁移** - SimpleMem 不提供 `get_all()` API |
| `DELETE /{user_id}` (清空) | 调用 `SimpleMemSystem(clear_db=True)` 重新初始化 |

### 步骤 3.2：修改 `routers/chat.py`

此文件是核心业务逻辑，涉及多处 `memory_service` 调用：

| 行号 | 原调用 | 改动 |
|------|--------|------|
| L155 | `memory_service.retrieve()` | 返回结构变化，需适配 |
| L309 | `memory_service.add_memory_item()` | 改为 `add_dialogue() + finalize()` |
| L512 | `memory_service.retrieve()` | 同上 |

---

## 第四阶段：移除 Graphiti/FalkorDB 特有逻辑

### 步骤 4.1：删除 Cypher 查询

以下代码段需完全删除或重写：

| 文件 | 行号范围 | 说明 |
|------|----------|------|
| `services/memory_service.py` | L313-L339 | `query_episodes` Cyper 查询 |
| `services/memory_service.py` | L359-L411 | `get_all()` 中的 Cypher 查询 |
| `services/memory_service.py` | L467 | `MATCH (n) DETACH DELETE n` |

### 步骤 4.2：删除调试/检查脚本

以下文件将失效，可删除或归档：

- `test_graphiti_compat.py`
- `deep_graph_analysis.py`
- `detailed_graph_check.py`
- `diagnose_graph_internal.py`
- `inspect_falkordb.py`
- `inspect_nodes_detail.py`
- `list_falkordb_graphs.py`
- `check_edges.py`
- `test_combined_query.py`

### 步骤 4.3：修改 `services/llm_logger.py`

删除 `configure_graphiti_logging()` 函数 (L200-L224)。

---

## 第五阶段：前端适配 (需要用户确认)

> [!IMPORTANT]
> **需要用户确认**:
> 前端目前是否依赖以下字段？

| 字段 | Graphiti 返回 | SimpleMem 返回 |
|------|---------------|----------------|
| `memories[].score` | ✅ 有 | ❌ 无 |
| `memories[].valid_at` | ✅ 有 | ❌ 无 |
| `memories[].invalid_at` | ✅ 有 | ❌ 无 |
| `memories[].created_at` | ✅ 有 | ❌ 无 |
| `episodes[]` | ✅ 有 | ❌ 无 (概念不存在) |

如果前端依赖这些字段，需要同步修改前端代码或提供兼容层。

---

## 无法迁移的功能

以下功能在 SimpleMem 中 **不存在等价物**，需要用户决定是否放弃：

| 功能 | Graphiti 实现 | SimpleMem 等价物 | 建议 |
|------|--------------|------------------|------|
| **时序知识图谱** | `valid_at`, `invalid_at` 追踪事实有效期 | ❌ 不支持 | 放弃或自行扩展 |
| **关系分组视图** | `grouped_history` 按关系类型分组 | ❌ 不支持 | 前端隐藏该功能 |
| **Episode 反查** | Edge → Episode 关联 | ❌ 不支持 | 前端隐藏该功能 |
| **列出所有记忆** | `get_all()` | ❌ 不支持 | 改用 `ask("列出我的所有信息")` 变通 |
| **污染注入 (DEBUG)** | `pollute_memory()` | 可自行实现 | 保留 |

---

## 迁移后的验证计划

### 自动化测试

运行现有测试（需先确认是否存在）：

```bash
# 检查是否有 pytest
pytest tests/ -v
```

### 手动测试

1. **添加记忆**:
   - 调用 `POST /memory/{user_id}/store` 存储一段对话
   - 预期：无错误返回

2. **检索记忆**:
   - 调用 `POST /memory/{user_id}/retrieve` 查询
   - 预期：返回相关记忆字符串

3. **完整对话流程**:
   - 调用 `POST /chat/{user_id}/interact` 进行多轮对话
   - 预期：记忆被正确存储，后续轮次能回忆起

---

## 时间估算

| 阶段 | 预计耗时 |
|------|----------|
| 依赖与环境 | 0.5 天 |
| 核心服务重写 | 1-2 天 |
| API 路由适配 | 0.5 天 |
| 移除旧代码 | 0.5 天 |
| 前端适配 (如需) | 1 天 |
| 测试与修复 | 1 天 |
| **总计** | **4-6 天** |

---

## 建议

根据以上分析，我仍然建议 **不要进行完整迁移**。原因：

1. SimpleMem 0.1.0 仍是早期版本，API 可能变动
2. 多租户隔离支持不明确
3. 你当前的 Graphiti + FalkorDB 架构更强大

**替代方案**: 从 SimpleMem 借鉴 "Memory Consolidation" 思想，在现有架构中实现后台整理任务。

---

## 需要用户确认的决策点汇总

1. **DashScope 兼容性**: SimpleMem 能否正常使用 `OPENAI_BASE_URL` 连接 DashScope?
2. **多租户隔离方案**: 路径隔离 / 共享 / 放弃迁移?
3. **前端字段依赖**: 是否依赖 `score`, `valid_at`, `episodes` 等字段?
4. **放弃的功能**: 是否接受放弃时序图谱、关系分组等高级功能?
5. **整体决策**: 是否继续迁移，还是采用"借鉴而非替换"策略?
