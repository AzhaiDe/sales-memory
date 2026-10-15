# Tool 文件夹架构分析

## 整体作用
**AI Agent工具库** — 为大语言模型提供可调用的外部工具接口，支持查询商品、订单、客户、宝宝月龄等业务数据。

---

## 文件1：tool.py（工具集成器）

### 主要职责
集中管理所有Agent可调用的工具，通过autogen_core的FunctionTool进行注册。

### 工具包装

```python
from autogen_core.tools import FunctionTool

search_goods_tool = FunctionTool(
    search_goods,
    name="search_goods",
    description="查询商品详情，以获取规格，适用症状，功效，使用方式等信息"
)
```

**作用**：将Python函数转化为LLM可调用的工具

### 工具字典

```python
tools = {
    "get_order_info_ybx": get_order_info_ybx,
    "get_contact_info_ybx": get_contact_info_ybx,
    "get_info_ybx": get_info_ybx
}
```

**用途**：LLM通过工具名称调用对应的函数

---

## 文件2：good.py（商品查询工具）

### 主要职责
提供商品查询的基础工具函数。

```python
async def search_goods(
    good_id: Optional[str | int],
    good_name: Annotated[str, "商品名称"]
) -> Annotated[str, "商品详情"]
```

**参数**：
- good_id：商品唯一ID（可选）
- good_name：商品名称（必需）

**返回**：商品详情字符串

**注意**：当前实现为示意性代码，返回"SEARCH GOODS"

---

## 文件3：ybx_contact_info.py（客户信息查询）

### 主要职责
查询YBX（一别相关）客户系统中的客户信息。

```python
async def get_contact_info_ybx(
    contact_id: str,
    tenant_id: str = "ybx",
    contact_name: str = "客户信息"
) -> dict
```

**查询过程**：
```
1. 获取RAG客户端
2. 构建过滤条件
   filters = [{"type": "equal", "condition": {"WID": [contact_id]}}]
3. 指定查询列
   ["会员姓名", "性别", "最小宝宝生日", "累计消费金额", ...]
4. 调用RAG搜索
5. 处理结果
```

**返回数据**：
```python
{
    "会员姓名": str,
    "性别": str,
    "最小宝宝生日": str,
    "累计消费金额": float,
    "累计购买次数": int,
    "平均客单价": float,
    "是否超级会员": bool,
    "会员剩余积分": int
}
```

**错误处理**：
- 查询返回code != 200时记录警告
- 未找到客户时记录警告
- 重复客户时记录警告

---

## 文件4：ybx_good_info.py（商品信息查询）

### 主要职责
查询YBX系统中的商品详情。

```python
async def get_good_info_ybx(
    sku_id: str,
    tenant_id: str = "ybx",
    good_name: str = "商品信息"
) -> dict
```

**查询字段**：
```
["消耗预估", "所属分类", "品牌", "适用月龄", 
 "适用症状", "子规格名称", "子规格条码"]
```

**返回数据**：
```python
{
    'sku_id': str,
    '子规格名称': str,
    '分类': str,
    '品牌': str,
    '适用月龄': str,
    '单件消耗': str,
    '适用症状': str
}
```

---

## 文件5：ybx_order_info.py（订单信息查询）

### 主要职责
查询YBX系统中客户的订单列表。

```python
async def get_order_info_ybx(
    contact_id: str,
    tenant_id: str = "ybx",
    order_name: str = "订单信息"
) -> list
```

**查询字段**：
```
["销售单号", "商品ID", "商品名称", "成交金额", 
 "商品成交数量", "成交时间"]
```

**返回数据**：订单列表，每条包含上述字段

---

## 文件6：ybx_query.py（复杂业务逻辑）

### 主要职责
综合聚合和处理客户、订单、商品数据，生成销售助手所需的信息。

### 核心函数：get_info_ybx()

```python
async def get_info_ybx(
    contact_id: str,
    tenant_id: str = "ybx",
    ...
) -> dict
```

**返回结构**：
```python
{
    "good_info": str,      # 商品信息
    "order_info": str,     # 订单信息
    "child_info": str      # 宝宝月龄信息
}
```

---

### 处理流程

**步骤1：获取订单数据**
```
get_order_info_ybx(contact_id)
  ↓
遍历每条订单，计算单价
  ↓
创建order_list
```

**步骤2：统计商品频率**
```
遍历订单（倒序）
  ├→ 标记最近订单
  ├→ 查询商品详情
  └→ 统计每个商品的购买次数
```

**步骤3：时间衰减调整**
```
对每个商品：
  └→ 根据距最后购买的天数调整频率
     公式：cnt -= floor(days / forget_cycle)
     forget_cycle = 30天
```

**步骤4：商品优先级筛选**
```
配置参数：
  - nearly = 10（最近订单范围）
  - goods_limit = 15（最多商品数量）
  - 有详情时最多5条订单
  - 无详情时最多3条订单
```

**步骤5：宝宝月龄计算**

这是ybx_query.py的核心创新——智能推断宝宝月龄：

```
核心假设：
  每个商品都有"适用月龄"范围
  客户购买某商品时，宝宝月龄必在该范围内

算法：
  1. 从订单提取"适用月龄"范围和下单时间
  2. 根据当前时间计算推断的月龄
  3. 与客户信息中的"最小宝宝生日"交叉验证
  4. 如果备注月龄符合推断范围，使用备注
  5. 否则使用推断范围

目的：
  推断当前客户宝宝的月龄范围，支持销售推荐
```

---

## 工具间协作流程

```
tool.py (工具注册)
  └─ 包装所有工具供LLM调用

ybx_contact_info.py ← RAG查询
  ↓ (客户基本信息)

ybx_order_info.py ← RAG查询
  ↓ (订单列表)

ybx_good_info.py ← RAG查询（按需）
  ↓ (商品详情)

ybx_query.py (复杂聚合)
  ├→ 调用上述三个函数
  ├→ 统计分析订单数据
  ├→ 智能推断宝宝月龄
  └→ 返回最终结果
```

---

## 核心算法：宝宝月龄推断

### __extract_child() 函数

**输入**：
- note：客户备注信息（如最小宝宝生日）
- order_child：从订单提取的月龄范围列表

**处理**：
1. 计算备注中宝宝的月龄
2. 从订单月龄推断当前月龄
3. 求所有商品适用月龄的交集
4. 区间合并（同一宝宝的不同月龄）
5. 验证备注是否在推断范围内

**返回**：
```python
[
    {
        "宝宝ID": "A",
        "月龄": "6-12(截至2026-06-16)"
    },
    ...
]
```

---

## 使用示例

### 场景：销售需要获取客户信息

```python
result = await get_info_ybx(
    contact_id="12345",
    tenant_id="ybx"
)

# 返回结果包含：
# - 客户购买过的所有商品（按优先级排序）
# - 最近的订单历史
# - 推断的宝宝月龄和身份

# 销售可以根据这些信息
# 进行个性化产品推荐
```

---

## 总结

**Tool文件夹 = LLM外部工具库**

### 文件分工

| 文件 | 职责 | 特点 |
|------|------|------|
| **tool.py** | 工具集成 | FunctionTool包装 |
| **good.py** | 基础工具 | 简单查询 |
| **ybx_contact_info.py** | 客户查询 | 单客户 |
| **ybx_order_info.py** | 订单查询 | 订单列表 |
| **ybx_good_info.py** | 商品查询 | 商品详情 |
| **ybx_query.py** | 复杂聚合 | 智能推断 |

### 核心创新

**宝宝月龄推断算法**：
- 利用商品"适用月龄"元数据
- 通过订单历史反推宝宝信息
- 支持多个宝宝场景
- 智能度量客户价值

### 架构优势

1. **工具化** — LLM可直接调用
2. **分层设计** — 从简到复
3. **智能推断** — 业务逻辑沉淀
4. **可扩展** — 易添加新工具
5. **RAG集成** — 连接外部知识库
