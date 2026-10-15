# Clients 文件夹架构分析

## 整体作用
**多数据源连接管理层** — 统一封装关系型数据库、向量数据库、缓存、嵌入向量服务和RAG服务的客户端接口。

---

## 各文件详解

### 第一部分：基础架构

#### 1. base.py（BaseClient基类）
**职责**：定义所有客户端的统一接口
- 抽象方法：connect()、close()、is_connected()
- client属性：自动连接检查和懒初始化
- 装饰器：trace_performance 记录方法耗时
- **设计模式**：Template Method + Lazy Loading

#### 2. factory.py（ClientFactory工厂）
**职责**：单一入口，统一管理所有客户端实例
```
get_mariadb_client()    → MariaDBClient.session
get_redis_client()      → RedisClient.redis
get_milvus_client()     → AsyncMilvusClient.milvus (async)
get_rag_client()        → RagClient.rag
close_all()             → 关闭所有连接
```
- **模式**：工厂 + 单例
- **优势**：解耦上层代码，统一管理生命周期

---

### 第二部分：本地数据存储

#### 3. mariadb.py（MariaDBClient）
**职责**：关系型数据库连接管理
- SQLAlchemy ORM + 连接池
- 配置：pool_size=30, max_overflow=10, recycle=3600s
- 单例模式保证一个进程只有一个连接
- **用途**：存储业务数据（用户、订单、配置等）

#### 4. redis.py（RedisClient）
**职责**：缓存层管理
- ConnectionPool连接池（max=50连接）
- 单例模式
- 配置：socket_timeout=5s, connect_timeout=5s
- **用途**：会话、缓存、临时数据

---

### 第三部分：向量数据存储

#### 5. milvus.py（MilvusClient + AsyncMilvusClient）
**职责**：向量数据库核心操作
分两个类：
- **MilvusClient**（同步）：基础CRUD
- **AsyncMilvusClient**（异步）：高并发支持

**核心操作**：
| 操作 | 功能 |
|------|------|
| insert/batch_insert | 插入新记录，自动ID生成 |
| upsert/batch_upsert | 更新或插入 |
| delete/batch_delete | 删除（支持批量） |
| filter_search | 条件查询（tenant/account/contact/category/theme） |
| vector_search | 向量相似度搜索（COSINE距离，HNSW索引） |
| drop_collection | 删除整个租户集合 |

**多租户支持**：
- 集合命名：`{prefix}{tenant_id}{suffix}`
- 租户隔离：每个租户独立集合
- 索引策略：
  - 向量字段：HNSW (M=16, efConstruction=64)
  - 标量字段：INVERTED索引（快速过滤）

**异步特性**：
- 使用asyncio.to_thread包装同步操作
- 引入asyncio.Lock防止并发冲突
- 集合缓存机制减少I/O

---

### 第四部分：外部服务接口

#### 6. embedding.py（EmbeddingClient）
**职责**：调用外部嵌入向量服务
- 通过gRPC调用（线程安全的通道复用）
- Consul服务发现（动态获取服务地址）
- 输入：文本列表 → 输出：向量列表（1024维）
- **模型**：bge-m3（默认）
- **用途**：theme_vector、fact_vector计算

#### 7. rag.py（RagClient）
**职责**：调用外部RAG（检索增强生成）服务
- 通过HTTP/aiohttp调用
- 两种模式：
  - `semantic`：语义搜索（向量匹配）
  - `table`：表格数据搜索
- 参数检验机制
- 支持分页（page_index、page_size）
- **用途**：智能检索相关知识、数据

---

## 整体协作架构

```
          Agent层（请求数据）
                 ↓
        ClientFactory（工厂）
                 ↓
     ┌──────────┬──────────┬──────────┬──────────┐
     ↓          ↓          ↓          ↓          ↓
  MariaDB    Redis      Milvus    Embedding    RAG
  (ORM关系)  (缓存)    (向量库)    (gRPC)    (HTTP)
  业务数据   临时数据  记忆向量   向量计算  知识检索
```

---

## 数据流示例

### 场景1：新增销售记忆
```
1. ExtractFactAgent 提取事实
   ↓
2. EmbeddingClient.get_embeddings()
   → 计算 theme_vector 和 fact_vector
   ↓
3. MilvusClient.insert()
   → 存储到向量数据库（+ 元数据索引）
   ↓
4. MariaDBClient
   → 记录操作日志
   ↓
5. RedisClient
   → 缓存最近查询
```

### 场景2：搜索相关记忆
```
1. RetrieveMemoryAgent 接收搜索请求
   ↓
2. EmbeddingClient.get_embeddings()
   → 查询文本转向量
   ↓
3. MilvusClient.vector_search()
   → 向量相似度排序（HNSW索引）
   或
   MilvusClient.filter_search()
   → 条件过滤（标量字段索引）
   ↓
4. 可选：RagClient.search()
   → 补充知识库信息
   ↓
5. 返回结果给Agent
```

---

## 关键设计特点

| 特性 | 实现 | 优势 |
|------|------|------|
| **单例模式** | 每个客户端只创建一次 | 避免多次连接，节省资源 |
| **工厂模式** | ClientFactory统一管理 | 解耦，便于测试和扩展 |
| **连接池** | MariaDB(30+10), Redis(50) | 支持高并发，复用连接 |
| **多租户隔离** | Milvus按tenant_id分集合 | SaaS应用中完全隔离 |
| **性能追踪** | @trace_performance装饰器 | 记录每个操作的耗时 |
| **异步支持** | AsyncMilvusClient | 高I/O并发场景下性能优 |
| **服务发现** | Consul集成 | 动态获取服务地址，灾备 |
| **连接回收** | pool_recycle=3600s | 防止长连接泄漏 |
| **批量操作** | batch_insert/batch_delete | 减少网络往返，提升吞吐 |

---

## 总结

Clients文件夹是一个**多数据源连接管理框架**：
- **横向扩展**：支持多种数据源（关系库、向量库、缓存、外部API）
- **纵向优化**：连接池、异步、缓存、性能追踪
- **多租户支持**：完全隔离不同租户的数据
- **统一接口**：通过工厂模式和单例模式提供一致的访问方式
