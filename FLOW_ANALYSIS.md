# Flow 文件夹架构分析

## 整体作用
**Agent编排引擎** — 根据不同的业务场景（在线/激活），编排多个Agent的执行流程，实现记忆的完整处理管道。

---

## 核心概念：两个Flow文件

### 架构对比

```
┌─────────────────────────────────────────┐
│         onlinememoryflow.py             │
│    （实时/在线处理流程）                 │
├─────────────────────────────────────────┤
│ 新增流程：                              │
│   AddMemoryRequest                      │
│   ↓                                     │
│   ExtractFactAgent (事实提取)          │
│   ↓                                     │
│   RetrieveMemoryAgent (历史检索)       │
│   ↓                                     │
│   ResolveConflictAgent (冲突解决)      │
│   ↓                                     │
│   AddMemoryResult                       │
│                                         │
│ 搜索流程：                              │
│   SearchMemoryRequest                   │
│   ↓                                     │
│   RetrieveMemoryAgent (搜索)           │
│   ↓                                     │
│   SearchMemoryResult                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│      activatememoryflow.py              │
│    （激活/批处理流程）                   │
├─────────────────────────────────────────┤
│ 新增流程：                              │
│   AddMemoryRequest                      │
│   ↓                                     │
│   ActivateMemAgent (主协调器)          │
│   ↓                                     │
│   ActivateMemStore (直接存储)          │
│   ↓                                     │
│   AddMemoryResult                       │
│                                         │
│ 搜索流程：                              │
│   SearchMemoryRequest                   │
│   ↓                                     │
│   ActivateMemStore (搜索)              │
│   ↓                                     │
│   SearchMemoryResult                    │
└─────────────────────────────────────────┘
```

---

## 文件1：onlinememoryflow.py（在线处理）

### 主要职责
处理实时对话场景，完整的记忆处理管道（提取→检索→冲突→存储）。

### add_memory_flow() 函数

**流程**：
```python
1. 创建runtime和输出队列
   ↓
2. 注册三个Agent：
   - ExtractFactAgent → topic: EXTRACT_FACT_AGENT
   - RetrieveMemoryAgent → topic: RETRIEVE_MEMORY_AGENT
   - ResolveConflictAgent → topic: RESOLVE_CONFLICT_AGENT
   ↓
3. 注册ClosureAgent → 接收最终结果
   ↓
4. 启动runtime
   ↓
5. 发布初始消息到 ExtractFactAgent
   ↓
6. 等待idle → 停止runtime
   ↓
7. 从队列获取结果并返回
```

**核心代码模式**：
```python
runtime = SingleThreadedAgentRuntime()

# 注册所有agent
await ExtractFactAgent.register(runtime, type=TopicType.EXTRACT_FACT_AGENT.value, ...)
await RetrieveMemoryAgent.register(runtime, type=TopicType.RETRIEVE_MEMORY_AGENT.value, ...)
await ResolveConflictAgent.register(runtime, type=TopicType.RESOLVE_CONFLICT_AGENT.value, ...)

# 发送启动消息
await runtime.publish_message(
    message=request_body,
    topic_id=TopicId(type=TopicType.EXTRACT_FACT_AGENT.value, source="default")
)

# 等待执行完成
await runtime.stop_when_idle()
```

### search_memory_flow() 函数

**流程简化**：
```
SearchMemoryRequest
  ↓
RetrieveMemoryAgent (向量搜索或条件查询)
  ↓
SearchMemoryResult
```

---

## 文件2：activatememoryflow.py（激活处理）

<br>

### 主要职责
处理后台批处理或激活场景，简化的记忆存储（直接存储，不需要完整的提取-检索-冲突流程）。

### add_memory_flow() 函数

**流程**：
```
AddMemoryRequest (已提取的事实)
  ↓
ActivateMemAgent (协调)
  ↓
ActivateMemStore (直接存储到Milvus)
  ↓
AddMemoryResult
```

**适用场景**：
- 批量记忆导入
- 预处理过的记忆数据
- 不需要实时冲突解决

### search_memory_flow() 函数

**流程简化**：
```
SearchMemoryRequest
  ↓
ActivateMemStore (查询Milvus)
  ↓
SearchMemoryResult
```

---

## 两个Flow的对比

### 业务场景区分

| 维度 | onlinememoryflow | activatememoryflow |
|------|-----------------|------------------|
| **场景** | 实时在线对话 | 后台批处理/激活 |
| **输入** | 原始对话数据 | 已结构化的记忆数据 |
| **处理流程** | 长链路（3个agent） | 短链路（1-2个agent） |
| **新增步骤数** | ExtractFact → Retrieve → ResolveConflict | 直接 ActivateMemStore |
| **搜索步骤数** | RetrieveMemory | ActivateMemStore |

### 执行效率

```
onlinememoryflow (新增):
  请求 → 提取事实(LLM) → 向量搜索(Milvus) → 冲突解决(LLM) → 存储 → 响应
  耗时：较长（涉及2次LLM调用）
  
activatememoryflow (新增):
  请求 → 直接存储 → 响应
  耗时：较短（无LLM调用）
```

---

## 通用设计模式

### Runtime生命周期

两个flow都遵循相同的Runtime管理模式：

```python
1. 创建runtime
   runtime = SingleThreadedAgentRuntime()
   
2. 注册所有agent（按业务流程注册）
   await Agent1.register(runtime, type="topic1", ...)
   await Agent2.register(runtime, type="topic2", ...)
   
3. 注册输出handler（ClosureAgent）
   await ClosureAgent.register_closure(runtime, type="closure", closure=output_result, ...)
   
4. 启动runtime
   runtime.start()
   
5. 发布启动消息
   await runtime.publish_message(message=request, topic_id=TopicId(...))
   
6. 等待所有agent执行完成
   await runtime.stop_when_idle()
   
7. 获取结果
   result = await queue.get()
```

### 异步消息队列

两个flow都使用asyncio.Queue实现结果回收：

```python
queue = asyncio.Queue[AddMemoryResult]()

async def output_result(_agent, message, ctx):
    await queue.put(message)  # 将结果放入队列

# ... runtime执行过程 ...

res = await queue.get()  # 等待结果
return res
```

### 性能追踪

两个flow都记录整个流程的耗时：

```python
start_time = time.time()
# ... 执行流程 ...
end_time = time.time()

logger.info(f"[PERF_METRICS][ONLINE/ACTIVATE] "
            f"flow=xxx_flow "
            f"tenant_id=... "
            f"duration={end_time - start_time:.2f}s")
```

---

## 整体工作流

### 应用启动时的选择

```
应用初始化
    ↓
选择记忆处理模式
    ├→ ONLINE (在线)
    │  使用 onlinememoryflow
    │  完整的AI驱动流程
    │
    └→ ACTIVATE (激活/批处理)
       使用 activatememoryflow
       轻量级存储流程
```

### 请求处理流程

**新增记忆**：
```
HTTP POST /add-memory
    ↓
controller 解析请求
    ↓
选择flow:
    ├→ onlinememoryflow.add_memory_flow() → 完整处理
    └→ activatememoryflow.add_memory_flow() → 直接存储
    ↓
返回 AddMemoryResult
```

**搜索记忆**：
```
HTTP POST /search-memory
    ↓
controller 解析请求
    ↓
选择flow:
    ├→ onlinememoryflow.search_memory_flow() → 详细检索
    └→ activatememoryflow.search_memory_flow() → 简单查询
    ↓
返回 SearchMemoryResult
```

---

## 设计特点

| 特性 | 实现方式 | 优势 |
|------|--------|------|
| **流程编排** | 使用autogen_core的Runtime | 灵活且类型安全 |
| **Agent隔离** | 独立的Runtime实例 | 每个请求独立运行，无状态 |
| **异步处理** | async/await全异步 | 高并发支持 |
| **消息路由** | TopicId自动路由 | Agent间解耦 |
| **性能监控** | 内置耗时记录 | 便于优化和调试 |
| **多模式** | 两个flow + 灵活选择 | 满足不同业务需求 |
| **结果收集** | ClosureAgent回调 | 保证结果可靠获取 |

---

## 总结

**Flow文件夹 = Agent编排和流程管理**

### 两个文件的角色

**onlinememoryflow.py**：
- 场景：实时在线处理
- 流程：完整的AI驱动流程
- 特点：支持复杂的逻辑处理（提取、检索、冲突解决）

**activatememoryflow.py**：
- 场景：后台批处理/激活
- 流程：简化的直接存储
- 特点：高效、轻量级

### 核心价值

1. **流程可视化** — 清晰的Agent执行顺序
2. **模块化** — 每个Agent独立职责
3. **可扩展** — 添加新Agent只需修改register
4. **性能优化** — 按场景选择不同的流程
5. **统一管理** — 相同的Runtime生命周期管理

### 使用方式

```python
# 根据业务场景选择
if mode == "online":
    result = await onlinememoryflow.add_memory_flow(request)
else:
    result = await activatememoryflow.add_memory_flow(request)
```

---

## 架构全景图

```
┌────────────────────────────────────────────────────┐
│              HTTP Controller                        │
│  POST /add-memory  或  POST /search-memory         │
└────────────────┬─────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
    ONLINE MODE      ACTIVATE MODE
         │                │
         ↓                ↓
┌─────────────────┐  ┌──────────────────┐
│onlinememory     │  │activatememory    │
│flow.py          │  │flow.py           │
│                 │  │                  │
│ 新增：          │  │ 新增：           │
│ ExtractFact→    │  │ ActivateMem→     │
│ Retrieve→       │  │ ActivateStore    │
│ ResolveConflict │  │                  │
│                 │  │ 搜索：           │
│ 搜索：          │  │ ActivateStore    │
│ Retrieve        │  │                  │
└────────┬────────┘  └────────┬─────────┘
         │                    │
         └────────┬───────────┘
                  ↓
        ┌──────────────────────┐
        │  Agent执行（via Runtime）
        │  - ExtractFactAgent
        │  - RetrieveMemoryAgent
        │  - ResolveConflictAgent
        │  - ActivateMemAgent
        │  - ActivateMemStore
        └────────┬─────────────┘
                 ↓
        ┌──────────────────────┐
        │  返回结果给Controller
        └──────────────────────┘
```

