# Sales Memory 项目本地复现指南

## 第一步：环境检查与准备

### 1. Python环境确认
```bash
# 检查Python版本
python --version  # 应显示 3.11.x

# 创建虚拟环境（推荐）
python -m venv sales_memory_env
source sales_memory_env/bin/activate  # Linux/WSL
# 或
# sales_memory_env\Scripts\activate  # Windows
```

### 2. 项目依赖分析

根据代码分析，您需要的核心依赖包括：

```
# 核心依赖
autogen-core>=0.2.0
autogen-ext>=0.2.0
pydantic>=2.0
sqlalchemy>=2.0
pymilvus>=2.4.0
redis>=5.0
grpcio>=1.50.0
grpcio-tools>=1.50.0

# LLM相关
transformers>=4.30.0
openai>=1.0.0
loguru>=0.7.0
python-consul>=1.1.0

# 数据处理
pandas>=2.0.0
openpyxl>=3.1.0
orjson>=3.9.0
jinja2>=3.1.0

# 时间处理
pytz>=2023.3
APScheduler>=3.10.0
```

### 3. 本地依赖服务

您需要本地运行或远程连接以下服务：

```
必需:
  ✓ Milvus (向量数据库)
  ✓ MariaDB (关系数据库)
  ✓ Redis (缓存)
  
可选（如果有远程）:
  □ Embedding服务 (可用外部API)
  □ RAG服务 (可用外部API)
  □ Consul (服务发现)
```

---

## 第二步：生成requirements.txt

```bash
# 在项目根目录创建requirements.txt
cat > requirements.txt << 'EOF'
# AutoGen框架
autogen-core==0.2.0
autogen-ext==0.2.0

# 数据处理和ORM
pydantic>=2.0
sqlalchemy>=2.0
pandas>=2.0

# 数据库驱动
pymilvus>=2.4.0
redis>=5.0
mysql-connector-python>=8.0

# gRPC
grpcio>=1.50.0
grpcio-tools>=1.50.0

# LLM和向量化
openai>=1.0.0
transformers>=4.30.0
python-consul>=1.1.0

# 日志和工具
loguru>=0.7.0
jinja2>=3.1.0
orjson>=3.9.0
openpyxl>=3.1.0
pytz>=2023.3
APScheduler>=3.10.0

# JSON修复
json-repair>=0.24.0
EOF

# 安装依赖
pip install -r requirements.txt
```

---

## 第三步：环境配置

### 1. 创建.env文件

在项目根目录创建 `.env`:

```
# 日志配置
LOG_PATH=./logs
LOG_LEVEL=INFO
LOG_MOD=console
LOG_MAX_SIZE=100
LOG_KEEP_DAYS=7
LOG_COMPRESS=false
LOG_AUTOGEN_LOGGING=normal

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8686
SERVER_WORKERS=1

# MariaDB配置
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=root
MARIADB_PASSWORD=your_password
MARIADB_DATABASE=sales_memory

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_USERNAME=
REDIS_PASSWORD=

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=minioadmin
MILVUS_PASSWORD=minioadmin
MILVUS_DATABASE=default
MILVUS_COLLECTION_PREFIX=memory_
MILVUS_POOL_SIZE=100

# Consul配置
CONSUL_HOST=localhost
CONSUL_PORT=8500
CONSUL_TYPE=json
CONSUL_CONFIG_ENABLED=false

# gRPC客户端配置
GRPC_CLIENT_SALES_EMBEDDING=localhost:8000
GRPC_CLIENT_SALES_RAG=localhost:8001

# LLM配置
PRIVATE_GPT_NAME=default
PRIVATE_GPT_API_BASE=https://api.openai.com/v1
PRIVATE_GPT_API_KEY=YOUR_API_KEY_HERE
PRIVATE_GPT_MODEL_NAME=gpt-3.5-turbo

ACTIVATE_GPT_NAME=qwq32b
ACTIVATE_GPT_API_BASE=https://api.openai.com/v1
ACTIVATE_GPT_API_KEY=YOUR_API_KEY_HERE
ACTIVATE_GPT_MODEL_NAME=gpt-3.5-turbo

# 定时任务配置
SCHEDULE_ENABLE=true

# 测试配置
TEST_ENABLE=false
TEST_OUTPUT_FILE=./output/test_results.xlsx
```

### 2. 加载环境变量

创建 `app/config/env_loader.py`:

```python
import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 获取环境变量的函数
def get_env(key: str, default: str = None) -> str:
    return os.getenv(key, default)
```

