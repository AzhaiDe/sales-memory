# Utils 文件夹架构分析

## 整体作用
**工具函数库** — 提供应用各层使用的通用工具函数和工具类，包括文本处理、时间转换、服务治理、数据导出、Token计算等。

---

## 文件1：chunk_utils.py（文本裁剪）

**chunk_chat_history()** — 根据Token限制智能裁剪聊天历史

```
原理：使用线性关系估算需要保留的文本长度
  保留比例 = (token - limit) / token
  保留长度 = 比例 * 原始长度 * 1.2(缩放)

流程：
  1. 计算需要保留的字符长度
  2. 按'\n'行边界裁剪
  3. 返回裁剪后的文本
```

---

## 文件2：common_utils.py（通用函数）

| 函数 | 功能 |
|------|------|
| **timestamp_to_datetime()** | 毫秒时间戳 → 上海时区datetime |
| **prompt_log()** | 将prompt信息序列化为JSON日志 |
| **extract_content()** | 正则提取`<answer>...</answer>`标签 |
| **get_memory_type()** | 内存类型 → Milvus集合后缀(`_online/_activate/_merge`) |

---

## 文件3：consul_utils.py（服务治理）

**Consul服务注册发现和健康检查**

| 函数 | 功能 |
|------|------|
| **get_service_ip_address()** | 获取本机IP（UDP连接法） |
| **microservice_register()** | 注册服务到Consul |
| **microservice_unregister()** | 从Consul注销服务 |
| **get_available_service(name)** | 获取可用服务列表 |
| **select_node_strategy()** | 选择节点（默认随机） |
| **get_service(name)** | 获取服务URL |

**流程**：
```
服务启动
  ├→ 获取本机IP
  ├→ 连接Consul
  └→ 注册TCP健康检查

服务调用
  ├→ 查询服务名
  ├→ 过滤健康实例
  └→ 随机选择一个节点
```

---

## 文件4：context_utils.py（上下文处理）

**ContextUtil类** — 处理protobuf Context，格式化为LLM可读文本

```
格式化规则：
  [客户][2026-06-16 12:00:00]：消息内容
  [销售][2026-06-16 12:01:00]：回复内容

方法：
  - _process_context()：格式化并保存
  - get_latest_customer_msg_with_timestamp()：获取最新客户消息
  - get_context_with_timestamp()：获取完整对话（按时间反向）
```

---

## 文件5：excel_utils.py（数据导出）

**ExcelUtils类** — 导出记忆操作结果到Excel（仅在test_enable=True时生效）

```
流程：
  1. _ensure_directory_exists() — 创建输出目录
  2. _ensure_file_exists() — 创建Excel文件和Sheet
  3. export_result() — 合并新数据并写入
```

**用途**：调试和分析，追踪操作记录

---

## 文件6：token_utils.py（Token计算）

**计算文本Token数，用于上下文窗口管理**

| 函数 | 功能 |
|------|------|
| **system_tokens(tokenizer, primary, critic)** | 计算system占用的token（取较长的+预留1K） |
| **user_tokens(tokenizer, data)** | 计算用户数据的token（支持List/String） |

---

## 六个文件的协作

```
context_utils(格式化)
  ↓ (Context → 格式文本)
chunk_utils(裁剪)
  ↓ (需要计算token数)
token_utils(计算)
  ↓ (返回token数)
  ↓
common_utils(通用)
  ├→ 时间转换
  ├→ 日志记录
  └→ 类型转换

consul_utils(服务发现)
  └→ 获取外部服务地址

excel_utils(导出)
  └→ 记录所有操作
```

---

## 总结

**Utils文件夹 = 工具函数库**

| 文件 | 职责 | 核心功能 |
|------|------|---------|
| **chunk_utils.py** | 文本裁剪 | 按Token限制智能裁剪 |
| **common_utils.py** | 通用工具 | 时间/日志/类型转换 |
| **consul_utils.py** | 服务治理 | 注册/发现/检查 |
| **context_utils.py** | 上下文处理 | 格式化对话历史 |
| **excel_utils.py** | 数据导出 | 导出到Excel |
| **token_utils.py** | Token计算 | 计算文本Token数 |

**核心价值**：
- 上下文管理（context → token → chunk）
- 服务治理（动态发现）
- 数据追踪（导出分析）
- 文本处理（格式化、裁剪、计算）
