# Config 文件夹架构分析

## 整体作用
**应用配置管理层** — 统一集中管理日志、服务器、数据库、向量库、外部服务等所有配置参数。

---

## 文件1：logger_setup.py（日志系统初始化）

### 主要职责
配置和初始化应用全局日志系统，支持多种输出形式和日志级别。

### 核心组件

**1. InterceptHandler类**
- 拦截Python标准库日志（logging）
- 将标准日志转发给loguru处理
- 作用：统一日志出口，避免日志分散

**2. configure_logging()函数**
- 参数：
  - `enable_trace`：是否启用TRACE级日志
  - `console_output`：是否输出到控制台（否则输出到文件）

- 日志输出配置：
  ```
  控制台模式 (MOD=console):
    输出 → stderr
    格式 → [时间] [级别] [文件:行号] [消息]
    彩色化 → 支持（绿色时间、红色ERROR等）
  
  文件模式 (MOD=file):
    输出 → {LOG_PATH}/{YYYY-MM-DD}.log
    轮转 → 按大小轮转 (MAX_SIZE MB)
    保留 → 保留N天 (KEEP_DAYS)
    压缩 → 可选gzip压缩
    异步 → enqueue=True (非阻塞)
  ```

- 日志过滤：
  - 当enable_trace=True时，包含TRACE_LOGGER_NAME日志
  - 否则只记录非TRACE日志

### 配置来源
从 `app.config.setting` 中的 `log_param` 获取配置参数。

### 自动初始化
```python
# 文件末尾自动执行
configure_logging(
    enable_trace=log_param.autogen_logging == 'trace',
    console_output=log_param.mod == 'console'
)
```
导入此模块时自动初始化日志系统。

---

## 文件2：setting.py（参数管理中心）

### 主要职责
统一管理应用所有配置参数，从settings模块读取配置并创建参数对象。

### 配置参数类（共11个）

#### 第一组：应用层配置

**1. LogParam** （日志配置）
```
path        → 日志文件路径
level       → 日志级别 (DEBUG/INFO/WARNING/ERROR)
max_size    → 日志文件最大大小 (MB)
keep_days   → 日志保留天数
compress    → 是否压缩
rotation    → 轮转策略
mod         → 输出模式 (console/file)
autogen_logging → autogen框架日志模式 (trace/normal)
```

**2. ServerParam** （Web服务器配置）
```
host        → 监听地址 (默认 0.0.0.0)
port        → 监听端口 (默认 8686)
workers     → 工作进程数 (默认 1)
```

#### 第二组：外部服务配置

**3. ConsulParam** （服务注册发现）
```
consul_host/port          → Consul服务器地址
consul_type               → 注册类型
consul_config_enabled     → 是否启用配置中心
consul_config_prefix      → 配置前缀
consul_discovery_register → 是否自动注册
consul_discovery_instance_id → 实例ID (默认UUID)
consul_discovery_service_name → 服务名
consul_discovery_ip_address → 服务IP
```

**4. GrpcClientParam** （gRPC服务地址）
```
sales_embedding_service_name  → 嵌入向量服务名
sales_rag_service_name        → RAG服务名
```

#### 第三组：数据库和向量库配置

**5. MariadbParam** （关系型数据库）
```
host/port/user/passwd/database
```

**6. RedisParam** （缓存）
```
host/port/db/username/passwd
```

**7. MilvusParam** （向量数据库）
```
host/port/user/password/database
collection_prefix    → 集合名前缀
pool_size           → 连接池大小
```

#### 第四组：LLM模型配置

**8. PrivateGPTParam** （私有GPT模型）
```
name        → 模型名称
api_base    → API基础URL
api_key     → 认证密钥
model_name  → 模型标识
```

**9. QwQ32BGPTParam** （QwQ-32B模型）
```
同PrivateGPTParam结构
```

#### 第五组：特殊功能配置

**10. ScheduleParam** （定时任务）
```
schedule_enable                    → 是否启用定时任务
delete_expired_memory_trigger      → 过期记忆删除触发器
delete_expired_memory_param        → 过期时间配置 (按主题分类)
```

**11. TestParam** （测试模式）
```
test_enable      → 是否启用测试
test_output_file → 测试结果输出文件
```

---

### 参数实例化

setting.py在模块级别创建所有配置对象的**全局单例**：

```python
# 创建实例
log_param = LogParam()
server_param = ServerParam()
consul_param = ConsulParam()
mariadb_param = MariadbParam()
redis_param = RedisParam()
milvus_param = MilvusParam()
grpc_client_param = GrpcClientParam()
schedule_param = ScheduleParam()
test_param = TestParam()

# 模型参数列表和字典（支持多模型）
model_param_list = [private_gpt_param, qwq32b_gpt_params]
model_param_dict = {param.name: param for param in model_param_list}
```

**访问方式**：
```python
from app.config.setting import log_param, mariadb_param, milvus_param

# 直接使用
db_host = mariadb_param.mariadb_host
log_level = log_param.level
```

---

## 整体协作流程

### 初始化顺序

```
1. 应用启动
   ↓
2. import app.config.logger_setup
   ↓
3. logger_setup导入log_param（从setting.py）
   ↓
4. configure_logging()自动执行
   → 读取log_param配置
   → 初始化日志系统
   ↓
5. 其他模块import配置参数（按需）
   ↓
6. Agent/Client使用配置参数
```

### 配置参数流向

```
settings (配置源)
    ↓
setting.py (参数适配层)
    ├→ LogParam
    ├→ ServerParam
    ├→ MariadbParam
    ├→ MilvusParam
    ├→ GrpcClientParam
    └→ ... (11个参数类)
    ↓
应用组件使用
    ├→ logger_setup (LogParam)
    ├→ ClientFactory (MariadbParam, RedisParam, MilvusParam)
    ├→ EmbeddingClient (GrpcClientParam)
    ├→ RagClient (GrpcClientParam)
    └→ Agents (模型参数dict)
```

---

## 设计特点

| 特性 | 实现方式 | 作用 |
|------|--------|------|
| **集中管理** | 所有参数在setting.py统一定义 | 便于维护和修改 |
| **参数类化** | 每个模块一个参数类 | 类型安全，IDE智能提示 |
| **全局单例** | 模块级实例化 | 整个应用共享配置，避免重复读取 |
| **配置分层** | settings → setting.py → 业务代码 | 解耦，便于配置中心集成 |
| **模型支持** | model_param_dict 字典 | 支持多模型切换 |
| **自动初始化** | configure_logging()自动执行 | 导入时自动完成日志初始化 |
| **日志多模式** | console/file + trace/normal | 开发/生产环境灵活切换 |

---

## 总结

**Config文件夹 = 应用配置统一入口**

**两个文件的角色**：
- **logger_setup.py** ：日志系统初始化（消费log_param）
- **setting.py** ：配置参数管理中心（提供log_param和其他参数）

**核心特点**：
1. 集中式管理 — 所有配置集中在setting.py
2. 参数类化 — 每个子系统配置封装为类
3. 全局单例 — 整个应用共享同一份配置
4. 自动初始化 — 日志系统导入时自动初始化
5. 灵活配置 — 支持开发/生产模式切换

**使用方式**：
```python
# 其他模块中
from app.config.setting import log_param, mariadb_param, milvus_param
from app.config.logger_setup import logger  # 已初始化的logger实例

# 直接使用
logger.info("message")
db_session = ClientFactory.get_mariadb_client()
```
