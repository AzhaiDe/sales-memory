# Enums 文件夹架构分析

## 整体作用
**类型和常数管理** — 统一定义应用中使用的所有枚举类型，包括agent主题、记忆类型、操作类型、发送者类型、提示模板等。

---

## 文件1：agent_topic.py（Agent通信协议）

### 主要职责
定义所有Agent之间的通信话题（Topic），用于event-driven架构中的消息路由。

### TopicType枚举

```python
EXTRACT_FACT_AGENT = "extract_fact_agent"
    ↓ Agent类型标识
    消费消息：AddMemoryRequest
    生成消息：AddMemoryAgent
    职能：从对话中提取结构化事实

RETRIEVE_MEMORY_AGENT = "retrieve_memory_agent"
    ↓
    消费消息：AddMemoryAgent
    生成消息：message with old_memory
    职能：向量搜索检索历史记忆

RESOLVE_CONFLICT_AGENT = "resolve_conflict_agent"
    ↓
    消费消息：AddMemoryAgent with old_memory
    生成消息：决策(ADD/UPDATE/DELETE)
    职能：冲突解决和新旧记忆合并

ACTIVATE_MEM_STORE = "activate_mem_store"
    ↓
    消费消息：冲突解决结果
    生成消息：AddMemoryResult
    职能：向Milvus存储最终记忆

ACTIVATE_MEM_AGENT = "activate_mem_agent"
    ↓
    职能：主协调器，编排上述agent流程

CLOSURE_AGENT = "closure_agent"
    ↓
    职能：清理和收尾
```

### 流程编排意义

这些TopicType通过@type_subscription装饰器，实现agent的自动路由和串行编排：

```
EXTRACT_FACT_AGENT (topic)
    ↓ publish to
RETRIEVE_MEMORY_AGENT (topic)
    ↓ publish to
RESOLVE_CONFLICT_AGENT (topic)
    ↓ publish to
ACTIVATE_MEM_STORE (topic)
    ↓ publish to
CLOSURE_AGENT (topic)
```

---

## 文件2：mem_types.py（记忆和操作类型）

### 主要职责
定义记忆的分类和对记忆的操作类型。

### MemType枚举（IntEnum）

```python
ONLINE = 0      → 在线记忆（实时对话产生）
ACTIVATE = 1    → 激活记忆（被唤醒/使用过）
MERGE = 2       → 合并记忆（多源数据合并）
```

**用途**：
- Milvus集合的后缀标识
- 区分不同类型的记忆存储
- 例如：集合名 = "memory_" + tenant_id + "_" + mem_type

### ActionType枚举

```python
ADD = "ADD"        → 新增记忆
UPDATE = "UPDATE"  → 更新记忆（修改内容）
DELETE = "DELETE"  → 删除记忆（冲突产生）
NONE = "NONE"      → 无操作（不需要更新）
```

**使用场景**：
- ResolveConflictAgent的冲突决策结果
- 指导后续的Milvus操作
- 维护记忆的操作历史

---

## 文件3：prompt_types.py（提示模板分类）

### 主要职责
集中管理所有LLM提示模板的标识符。

### PromptType枚举

```python
EXTRACT_FACT = "extract_fact"
    → 从对话提取事实的prompt
    消费者：ExtractFactAgent
    
RESOLVE_CONFLICT = "resolve_conflict"
    → 解决新旧记忆冲突的prompt
    消费者：ResolveConflictAgent
    
REWRITE_QUERY = "rewrite_query"
    → 改写用户查询语句的prompt
    消费者：RetrieveMemoryAgent
```

**使用方式**：
```python
prompt = self.get_prompt(
    tenant_id="xxx",
    prompt_name=PromptType.EXTRACT_FACT.value,  # "extract_fact"
    synopsis={"context": "..."}
)
```

---

## 文件4：sender_types.py（消息发送者）

### 主要职责
定义对话中的参与者类型。

### SenderType枚举

```python
SALESMAN = 'salesman'   → 销售人员
CUSTOMER = 'customer'   → 客户/用户
```

### 特殊方法

**get_value()** - 转换为中文显示：
```python
SenderType.SALESMAN.get_value() → "销售"
SenderType.CUSTOMER.get_value() → "客户"
```

**使用场景**：
- 对话上下文解析（识别谁在说话）
- 记忆提取时的角色标记
- 日志和报告中的中文显示

---

## 整体关系图

```
枚举管理层
│
├─ agent_topic.py
│  └─ TopicType
│     用于：@type_subscription(topic_type=TopicType.XXX.value)
│     作用：agent间通信路由
│
├─ mem_types.py
│  ├─ MemType
│  │  用于：Milvus集合后缀
│  │  示例：memory_tenant1_1 (ACTIVATE)
│  │
│  └─ ActionType
│     用于：ResolveConflictAgent决策
│     示例：{"action": ActionType.UPDATE.value}
│
├─ prompt_types.py
│  └─ PromptType
│     用于：get_prompt(prompt_name=PromptType.XXX.value)
│     作用：加载对应的prompt模板
│
└─ sender_types.py
   └─ SenderType
      用于：context.role == SenderType.SALESMAN.value
      作用：识别对话参与者类型
```

---

## 设计特点

| 特性 | 实现 | 优势 |
|------|------|------|
| **集中管理** | 所有枚举在enums文件夹 | 便于查看全局定义 |
| **类型安全** | 使用Enum替代字符串 | 避免typo，IDE智能提示 |
| **IntEnum** | MemType用IntEnum | 可直接进行数值操作 |
| **值转换** | SenderType.get_value() | 支持多语言展示 |
| **可读性** | 每个枚举详细注释 | 便于维护 |

---

## 使用示例

### 场景1：Agent消息路由
```python
@type_subscription(topic_type=TopicType.EXTRACT_FACT_AGENT.value)
class ExtractFactAgent(BaseAgent):
    @message_handler
    async def handle_add_memory(self, message, ctx):
        # 处理逻辑
        await self.publish_message(
            result,
            topic_id=TopicId(TopicType.RETRIEVE_MEMORY_AGENT.value, source=self.id.key)
        )
```

### 场景2：记忆操作
```python
# 决策什么操作
action = resp.get("action", ActionType.ADD.value)
if action == ActionType.UPDATE.value:
    delete_memory_list.append(memory_id)
```

### 场景3：Prompt加载
```python
prompt = self.get_prompt(
    tenant_id=message.tenant_id,
    prompt_name=PromptType.EXTRACT_FACT.value,
    synopsis={"context": context}
)
```

### 场景4：发送者识别
```python
for context in request_body.contexts:
    role = "销售" if context.role == SenderType.SALESMAN.value else "客户"
```

---

## 总结

**Enums文件夹 = 应用类型系统的骨架**

**4个文件的分工**：
- **agent_topic.py** → Agent通信协议
- **mem_types.py** → 记忆分类和操作类型
- **prompt_types.py** → LLM提示模板
- **sender_types.py** → 对话参与者

**核心价值**：
1. 类型安全 — 避免魔法字符串
2. 可读性强 — 清晰的业务语义
3. 可维护性 — 修改集中，影响全局
4. IDE支持 — 自动补全、跳转
