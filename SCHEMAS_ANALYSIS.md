# Schemas 文件夹架构分析

## 整体作用
**数据模型定义层** — 定义应用中所有数据结构，包括API请求/响应、数据库表结构、向量库集合结构、Prompt数据等。

---

## 文件1：body.py（API数据模型）

### 主要职责
使用Pydantic定义API请求和响应的数据模型，支持自动验证和序列化。

### 基础类：FinalResult

```python
class FinalResult(BaseModel):
    error_msg: str = ""        # 错误消息
    status_code: int = 0       # 状态码
```

**作用**：所有Agent输出结果的基类

---

### 基础类：MemoryAgent

```python
class MemoryAgent(BaseModel):
    tenant_id: constr(min_length=3, strip_whitespace=True)
    contact_id: constr(strip_whitespace=True)
    account_id: constr(strip_whitespace=True)
    type: str = ""
```

**字段验证**：
- tenant_id：最少3个字符
- 自动去除首尾空格
- type：记忆类型（ONLINE/ACTIVATE/MERGE）

**作用**：所有Agent入参的基类，包含租户、客户、销售ID

---

### 派生类：AddMemoryAgent

```python
class AddMemoryAgent(MemoryAgent):
    contexts: List[Any]                    # 对话上下文列表
    context: str = ""                      # 合并后的上下文
    fact: List[Dict[str, Any]] = {}        # 提取的事实
    old_memory: List[Any] = []             # 历史记忆
    new_memory: List[Any] = []             # 新记忆
```

**数据流**：
- 输入：contexts（对话）
- 处理：context（合并）→ fact（提取）
- 中间：old_memory（检索）
- 输出：new_memory（决策后）

---

### 派生类：AddMemoryResult

```python
class AddMemoryResult(FinalResult):
    memory: List[Any] = []     # 新增的记忆列表
```

**用途**：新增记忆API的响应

---

### 派生类：SearchMemoryResult

```python
class SearchMemoryResult(FinalResult):
    memory: List[Any] = []     # 检索到的记忆列表
```

**用途**：搜索记忆API的响应

---

## 文件2：db_schema.py（数据库表结构）

### 主要职责
定义关系数据库（MariaDB）的表结构和ORM模型。

### Base 基类

```python
class Base(DeclarativeBase):
    updated_by = Column(String(255))      # 更新者
    created_by = Column(String(255))      # 创建者
    create_time = TIMESTAMP (自动)         # 创建时间
    update_time = TIMESTAMP (自动更新)     # 更新时间
```

**设计特点**：
- 所有表都继承Base，自动包含审计字段
- create_time/update_time自动管理
- 支持数据追踪和版本管理

---

### ActivateMemoryEntity 表

```python
class ActivateMemoryEntity(Base):
    __tablename__ = "t_activate_memory"
    
    id = BigInteger (自增主键)
    tenant_id = VARCHAR (租户ID)
    prompt_config = Text (Prompt配置)
    resource_config = Text (资源配置)
```

**字段说明**：
- id：自增主键
- tenant_id：租户隔离
- prompt_config：存储Prompt相关配置（避免过长）
- resource_config：存储外部资源配置（如知识库引用）

**用途**：存储激活记忆的配置信息

---

## 文件3：milvus_schemas.py（向量库集合结构）

### 主要职责
定义Milvus向量数据库的集合结构和数据类。

### MemorySchemaData 数据类

```python
@dataclass
class MemorySchemaData(MemorySchemaBase):
    tenant_id: str             # 租户ID
    account_id: str            # 销售ID
    contact_id: str            # 客户ID
    category: str              # 一级标签
    theme: str                 # 二级标签
    fact: list                 # 三级标签（事实列表）
    history: list              # 操作历史
    occur_time: int            # 发生时间（时间戳）
    expire_time: int           # 过期时间（时间戳）
    update_time: int           # 更新时间（时间戳）
    theme_vector: list         # 话题向量 (1024维)
    fact_vector: list          # 事实向量 (1024维)
```

**分类**：
- 过滤字段：tenant_id, account_id, contact_id, category, theme
- 内容字段：fact (ARRAY), history (ARRAY)
- 时间字段：occur_time, expire_time, update_time
- 向量字段：theme_vector, fact_vector (1024维)

---

### get_memory_schema() 函数

**Milvus集合定义**：

```
字段配置：
├─ 主键字段
│  └─ id (INT64, 自增)
├─ 过滤字段 (VARCHAR)
│  ├─ tenant_id (max_length=100)
│  ├─ account_id (max_length=100)
│  ├─ contact_id (max_length=100)
│  ├─ category (max_length=1000)
│  └─ theme (max_length=1000)
├─ 内容字段 (ARRAY)
│  ├─ fact (max_capacity=4096, VARCHAR)
│  └─ history (max_capacity=4096, VARCHAR)
├─ 时间字段 (INT64)
│  ├─ occur_time
│  ├─ expire_time
│  └─ update_time
└─ 向量字段 (FLOAT_VECTOR)
   ├─ theme_vector (dim=1024)
   └─ fact_vector (dim=1024)
```

**索引策略**（在milvus.py中创建）：
- theme_vector：HNSW索引 (M=16, efConstruction=64)
- fact_vector：HNSW索引 (M=16, efConstruction=64)
- 标量字段：INVERTED索引（快速过滤）

---

## 文件4：prompt_data.py（Prompt数据结构）

<thinking>

现在我需要继续分析prompt_data.py文件。这个文件定义了Prompt输入数据的结构和资源配置。让我继续编辑文件。
</thinking>

### 主要职责
定义Prompt模板的输入数据结构和资源配置。

### PromptInputBase 基类

```python
@dataclass
class PromptInputBase:
    def to_dict(self):
        return asdict(self)  # 转换为字典
```

**作用**：Prompt输入数据的基类，支持to_dict()转换

---

### ExtractFactData (提取事实)

```python
@dataclass
class ExtractFactData(PromptInputBase):
    context: str    # 对话上下文
```

**用途**：ExtractFactAgent的Prompt输入
```
Prompt模板：
  "从以下对话中提取关键信息"
  "对话内容：{{ context }}"
```

---

### ResolveConflictData (冲突解决)

```python
@dataclass
class ResolveConflictData(PromptInputBase):
    old_memory: List[Any]      # 历史记忆列表
    new_info: List[Any]        # 新提取的信息
```

**用途**：ResolveConflictAgent的Prompt输入
```
Prompt模板：
  "比对新旧记忆，决策处理方式"
  "历史记忆：{{ old_memory }}"
  "新信息：{{ new_info }}"
```

---

### RewriteQueryData (改写查询)

```python
@dataclass
class RewriteQueryData(PromptInputBase):
    context: str        # 对话上下文
    latest_msg: str     # 最新消息
```

**用途**：RetrieveMemoryAgent的Prompt输入
```
Prompt模板：
  "改写用户查询语句"
  "上下文：{{ context }}"
  "最新消息：{{ latest_msg }}"
```

---

### PromptConfig (Prompt配置)

```python
@dataclass
class PromptConfig(object):
    role: str          # 角色
    name: str          # 名称
    config: any        # 配置字典
```

**方法**：
- to_dict()：转换为字典
- to_class()：从字典创建实例

---

### ResourceConfig (资源配置)

```python
@dataclass
class ResourceConfig(object):
    @dataclass
    class Knowledge(object):
        name: str      # 知识库名称
        role: str      # 角色
        tool: str      # 工具类型
        params: any    # 工具参数
    
    knowledge: list[Knowledge]    # 知识库列表
```

**嵌套结构**：
```
ResourceConfig
  └─ knowledge: List[Knowledge]
     ├─ name: 知识库名称
     ├─ role: 角色描述
     ├─ tool: 调用的工具
     └─ params: 工具参数
```

**方法**：
- to_dict()：转换为字典
- to_class()：从字典创建实例，递归创建Knowledge子类

---

## 四个文件的协作

```
body.py (API数据模型)
  ├─ AddMemoryAgent (请求)
  └─ AddMemoryResult (响应)
      ↑
      ├─ 在Agent间流转
      └─ MemoryAgent (基类)

db_schema.py (关系数据库)
  └─ ActivateMemoryEntity
     存储：prompt_config, resource_config

milvus_schemas.py (向量数据库)
  └─ MemorySchemaData
     存储：记忆的完整数据
     包括：文本、向量、时间等

prompt_data.py (Prompt数据)
  ├─ ExtractFactData
  ├─ ResolveConflictData
  ├─ RewriteQueryData
  ├─ PromptConfig
  └─ ResourceConfig
     用于：Prompt渲染输入
```

---

## 数据流示例

### 新增记忆流程的数据变化

```
1. 请求阶段
   body.py: AddMemoryRequest
   {tenant_id, account_id, contact_id, contexts, type}
   
2. Agent处理阶段
   body.py: AddMemoryAgent
   {contexts + context + fact + old_memory + new_memory}
   
3. 存储阶段
   db_schema.py: ActivateMemoryEntity
   存储激活配置信息
   
   milvus_schemas.py: MemorySchemaData
   存储完整记忆数据（含向量）
   
4. Prompt渲染
   prompt_data.py: ExtractFactData/ResolveConflictData
   {context, old_memory, new_info}
   
5. 响应阶段
   body.py: AddMemoryResult
   {memory, error_msg, status_code}
```

---

## 总结

**Schemas文件夹 = 完整的数据模型定义**

### 四个文件的角色

**body.py**：
- API请求/响应模型
- Pydantic自动验证
- Agent间数据传输

**db_schema.py**：
- MariaDB表结构
- SQLAlchemy ORM
- 配置数据持久化

**milvus_schemas.py**：
- Milvus集合结构
- 记忆数据存储
- 向量索引定义

**prompt_data.py**：
- Prompt输入结构
- 资源配置定义
- Jinja2模板渲染

### 核心价值

1. **类型安全** — Pydantic和dataclass确保数据一致性
2. **自动验证** — 字段约束自动检查
3. **多存储适配** — API/关系库/向量库统一定义
4. **易于扩展** — 基类继承支持快速添加新类型
5. **数据追踪** — 审计字段自动管理

### 使用层次

```
系统边界
  ↑
API层 (body.py)
  ↓ (request)
业务逻辑 (Agents)
  ├→ prompt_data.py (Prompt渲染)
  └→ db_schema.py (配置存储)
     milvus_schemas.py (记忆存储)
```
