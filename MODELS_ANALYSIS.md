# Models 文件夹架构分析

## 整体作用
**LLM模型管理层** — 统一管理模型客户端的创建、缓存、配置，以及Prompt模板的加载和渲染。

---

## 文件1：model_config.py（配置抽象）

### ModelClientConfig（抽象基类）
```python
@abstractmethod get_model_name() → 模型名称
@abstractmethod get_model_params() → 模型参数字典
```

### PrivateGPTConfig（具体实现）
配置参数：
- model_name：模型标识
- api_base：API服务地址
- api_key：认证密钥
- model_info：模型能力（vision/function_calling/json_output/family）

---

## 文件2：factory.py（工厂和客户端管理）

### ModelClientConfigFactory
```
_instances: 配置缓存
create_config(config_name) → 创建PrivateGPTConfig
get_config(config_name) → 获取/缓存配置
```

### ModelClientFactory
```
_instances: 客户端缓存
_tokenizer_instances: tokenizer缓存
_client_types: 支持的客户端类型

create_client(config) → 创建客户端实例
get_client(config) → 获取/缓存客户端
get_default_client() → 获取默认客户端
get_client_by_name(model_name) → 按名称获取
get_tokenizer(config) → 获取tokenizer
clear_cache() → 清除缓存
```

---

## 文件3：prompt_manager.py（Prompt管理）

### 核心函数
```
_render_str(content, synopsis) → Jinja2渲染字符串
_render_file(file, synopsis) → 读取文件后渲染
```

### PromptManager类
```
__init__(tenant_id)
  _prompt_path = "{base}/prompts/{tenant_id}"

load_prompt(prompt_name, synopsis={})
  1. 检查自定义prompt路径
  2. 如果存在使用自定义，否则用默认
  3. 使用Jinja2渲染
  4. 返回渲染结果
```

**租户隔离**：每个tenant有独立的prompt目录

---

## 三个文件的协作流程

```
model_config.py (配置定义)
    ↓ (定义接口和实现)
    ↓
factory.py (创建和缓存)
    ├→ ModelClientConfigFactory.get_config()
    │  └→ 返回PrivateGPTConfig实例
    │
    ├→ ModelClientFactory.get_client()
    │  └→ 返回ChatCompletionClient实例
    │
    └→ ModelClientFactory.get_tokenizer()
       └→ 返回Tokenizer实例

                ↓
            Agent使用
            ├→ 获取LLM客户端进行推理
            └→ 获取tokenizer计算token数
            

prompt_manager.py (Prompt管理)
    ↓
PromptManager(tenant_id)
    ├→ 按租户加载prompt
    ├→ 使用Jinja2模板渲染
    └→ 返回最终prompt

                ↓
            Agent使用
            ├→ get_prompt()获取渲染的prompt
            └→ 传给LLM客户端进行推理
```

---

## 关键设计特点

| 特性 | 实现 | 优势 |
|------|------|------|
| **配置抽象** | ModelClientConfig基类 | 支持多模型扩展 |
| **单例缓存** | _instances字典 | 避免重复创建，节省资源 |
| **多模型支持** | _client_types映射 | 灵活切换模型 |
| **模板引擎** | Jinja2渲染 | 强大的变量替换能力 |
| **租户隔离** | 按tenant_id隔离prompt | 支持多租户定制 |
| **自定义支持** | 优先使用自定义prompt | 灵活覆盖默认配置 |

---

## 使用示例

### 获取LLM客户端
```python
from app.models.factory import ModelClientFactory

# 获取默认客户端
client = ModelClientFactory.get_default_client()

# 或按名称获取
client = ModelClientFactory.get_client_by_name("qwq-32b")

# 使用客户端
result = await client.create(messages=[...])
```

### 加载和渲染Prompt
```python
from app.models.prompt_manager import PromptManager

pm = PromptManager(tenant_id="tenant_123")

prompt = pm.load_prompt(
    "extract_fact",
    synopsis={"context": "...", "format": "JSON"}
)

# 使用prompt与LLM交互
result = await client.create(messages=[UserMessage(content=prompt)])
```

### 获取Tokenizer
```python
tokenizer = ModelClientFactory.get_tokenizer(config)
token_count = len(tokenizer.encode(text))
```

---

## 总结

**Models文件夹 = LLM管理中心**

### 三个文件的角色
- **model_config.py** ：配置定义和接口规范
- **factory.py** ：创建、缓存、管理模型客户端
- **prompt_manager.py** ：加载、渲染、管理Prompt

### 核心价值
1. **统一接口** — 所有模型操作通过factory获取
2. **灵活配置** — 支持多模型和自定义参数
3. **缓存优化** — 单例缓存避免重复创建
4. **Prompt管理** — 集中管理和渲染Prompt
5. **租户隔离** — 支持多租户的自定义Prompt
6. **易于扩展** — 新增模型只需继承基类
