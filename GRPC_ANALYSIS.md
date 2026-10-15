# gRPC 文件夹架构分析

## 整体作用
**外部服务接口层** — 定义记忆体服务的gRPC接口规范和实现，作为应用的网络入口。

---

## 文件1：salesmemory.proto（接口合约）

### 主要职责
使用Protocol Buffers定义MemoryService的gRPC接口规范和消息结构。

### gRPC Service 定义

```protobuf
service MemoryService {
  rpc AddMemories (AddMemoryRequests) returns (AddMemoryResponses);
  rpc AddMemory (AddMemoryRequest) returns (AddMemoryResponse);
  rpc SearchMemory (SearchMemoryRequest) returns (SearchMemoryResponse);
}
```

**三个RPC方法**：

1. **AddMemories** (批量新增)
   ```
   输入：AddMemoryRequests (包含多个AddMemoryRequest)
   输出：AddMemoryResponses (包含多个AddMemoryResponse)
   用途：支持批量操作，提高吞吐量
   ```

2. **AddMemory** (单个新增)
   ```
   输入：AddMemoryRequest
   输出：AddMemoryResponse
   用途：单个记忆新增
   ```

3. **SearchMemory** (搜索)
   ```
   输入：SearchMemoryRequest
   输出：SearchMemoryResponse
   用途：记忆搜索和检索
   ```

### 消息结构定义

**核心消息：Memory（记忆结构）**
```protobuf
message Memory {
  int64 id = 1;              // 记忆ID
  string category = 2;       // 一级标签（信息类型）
  string theme = 3;          // 二级标签（话题）
  repeated string fact = 4;  // 三级标签（事实内容）
  int64 occur_time = 5;      // 发生时间
}
```

---

### AddMemoryRequest (新增请求)

```protobuf
message AddMemoryRequest {
  string tenant_id = 1;          // 租户ID
  string account_id = 2;         // 销售ID
  string contact_id = 3;         // 客户ID
  repeated Context contexts = 4; // 对话上下文
  int32 type = 5;                // 记忆类型(0:ONLINE, 1:ACTIVATE, 2:MERGE)
  map<string, string> external_info = 6; // 外部扩展信息
}
```

**关键字段**：
- `type`：控制处理流程选择（ONLINE vs ACTIVATE）
- `contexts`：对话历史列表
- `external_info`：灵活扩展

### Context (对话上下文)

```protobuf
message Context {
  string content = 1;   // 消息内容
  string msgType = 2;   // 消息类型
  string role = 3;      // 发送者（销售/客户）
  string url = 4;       // 附件URL
  int64 msgTime = 5;    // 消息时间戳
}
```

---

### SearchMemoryRequest (搜索请求)

```protobuf
message SearchMemoryRequest {
  string tenant_id = 1;          // 租户ID
  string account_id = 2;         // 销售ID
  string contact_id = 3;         // 客户ID
  repeated Context contexts = 4; // 对话上下文
  string latest_msg = 5;         // 最新消息或经验描述
  string category = 6;           // 一级标签（可选）
  string theme = 7;              // 二级标签（可选）
  int32 type = 8;                // 记忆类型
  int32 mode = 9;                // 检索模式(0:全量, 1:条件)
}
```

**mode参数**：
- `0`：无条件检索所有记忆
- `1`：基于话题和事实的条件检索

---

## 文件2：memory_service.py（服务实现）

### 主要职责
实现salesmemory.proto定义的MemoryService接口，连接gRPC层和业务逻辑层。

### MemoryService 类结构

```python
class MemoryService(MemoryServiceServicer):
    async def AddMemories(...)        # 批量新增
    async def AddMemory(...)          # 单个新增
    async def SearchMemory(...)       # 搜索
```

---

### 方法1：AddMemories（批量新增）

**流程**：
```python
1. 接收AddMemoryRequests（包含多个AddMemoryRequest）
   ↓
2. 为每个request创建task
   tasks.append(self.AddMemory(request, context))
   ↓
3. 并发执行所有task
   responses = await asyncio.gather(*tasks)
   ↓
4. 返回AddMemoryResponses（包含所有响应）
```

**代码核心**：
```python
async def AddMemories(self, requests: AddMemoryRequests, context):
    tasks = []
    for request in requests.requests:
        tasks.append(self.AddMemory(request, context))
    
    responses = await asyncio.gather(*tasks)  # 并发执行
    return AddMemoryResponses(response=responses)
```

**性能优势**：
- 使用asyncio.gather实现并发处理
- 多个请求同时执行，大幅提高吞吐量

---

### 方法2：AddMemory（单个新增）

**流程**：
```
1. 日志记录（请求接收）
   ↓
2. 根据request.type选择flow
   ├→ type == ACTIVATE (1)  → activate_add_memory_flow
   └→ type == ONLINE (0)    → online_add_memory_flow
   ↓
3. 执行选中的flow
   res: AddMemoryResult = await flow(request)
   ↓
4. 异常处理
   ├→ 业务异常：返回AddMemoryResponse()，设置error_msg
   └→ 系统异常：捕获Exception，设置UNKNOWN_ERROR
   ↓
5. 构建响应
   response = AddMemoryResponse(memory=res.memory)
   ↓
6. 日志记录（请求完成）
```

**核心逻辑**：
```python
async def AddMemory(self, request: AddMemoryRequest, context):
    try:
        # 选择flow
        if MemType.ACTIVATE == request.type:
            res = await activate_add_memory_flow(request)
        else:
            res = await online_add_memory_flow(request)
        
        # 检查业务错误
        if res.error_msg:
            context.set_code(res.status_code)
            context.set_details(res.error_msg)
            return AddMemoryResponse()
        
        # 返回成功响应
        return AddMemoryResponse(memory=res.memory)
    
    except Exception as e:
        context.set_code(ErrorCode.UNKNOWN_ERROR.code)
        context.set_details(str(e))
        return AddMemoryResponse()
```

---

### 方法3：SearchMemory（搜索）

**流程**：
```
1. 日志记录（请求接收）
   ↓
2. 根据request.type选择flow
   ├→ type == ACTIVATE  → activate_search_memory_flow
   └→ type == ONLINE    → online_search_memory_flow
   ↓
3. 执行选中的flow
   res: SearchMemoryResult = await flow(request)
   ↓
4. 异常处理
   ├→ 业务异常：返回AddMemoryResponse()，设置error_msg
   └→ 系统异常：捕获Exception，设置UNKNOWN_ERROR
   ↓
5. 构建响应
   response = AddMemoryResponse(memory=res.memory)
   ↓
6. 日志记录（请求完成）
```

---

## 整体工作流程

### 请求处理流程

```
gRPC客户端
    ↓
[MemoryService.AddMemory]
    ├→ 日志：接收请求信息
    ├→ 流程选择
    │  ├→ type=ACTIVATE → activate_add_memory_flow()
    │  └→ type=ONLINE → online_add_memory_flow()
    ├→ 异常处理
    │  ├→ 业务异常 (res.error_msg) → gRPC error
    │  └→ 系统异常 (Exception) → UNKNOWN_ERROR
    ├→ 响应构建
    │  └→ AddMemoryResponse(memory=...)
    └→ 日志：完成请求
    ↓
gRPC客户端（返回响应）
```

### 批量处理流程

```
gRPC客户端
    ↓
[MemoryService.AddMemories]
    ├→ 提取多个request
    ├→ 为每个request创建task
    ├→ 使用asyncio.gather并发执行
    │  └→ 所有AddMemory并发运行
    ├→ 收集所有响应
    └→ 返回AddMemoryResponses
    ↓
gRPC客户端（返回多个响应）
```

---

## 关键设计特点

| 特性 | 实现 | 优势 |
|------|------|------|
| **协议** | Protocol Buffers | 跨语言、向后兼容 |
| **RPC模型** | 异步/await | 高并发支持 |
| **流程路由** | 根据type选择flow | 灵活支持多种模式 |
| **批量处理** | asyncio.gather | 并发执行，提高吞吐 |
| **异常处理** | 业务异常+系统异常分离 | 错误定位清晰 |
| **性能监控** | 完整的日志记录 | 便于调试和优化 |
| **gRPC状态** | context.set_code/set_details | 标准gRPC错误传递 |

---

## Proto与Service的协作

```
salesmemory.proto (接口合约)
    ↓
protoc编译生成
    ├→ salesmemory_pb2.py (消息类)
    └→ salesmemory_pb2_grpc.py (服务基类)
    ↓
memory_service.py (实现)
    ├→ 继承MemoryServiceServicer
    ├→ 实现AddMemories、AddMemory、SearchMemory
    └→ 返回protobuf消息对象
```

---

## 使用示例

### 客户端调用示例

```python
# 创建gRPC通道
channel = grpc.aio.secure_channel('localhost:8686', credentials)
stub = MemoryServiceStub(channel)

# 单个新增
request = AddMemoryRequest(
    tenant_id="tenant1",
    account_id="sales1",
    contact_id="customer1",
    contexts=[...],
    type=MemType.ONLINE
)
response = await stub.AddMemory(request)

# 批量新增
requests = AddMemoryRequests(requests=[request1, request2, request3])
responses = await stub.AddMemories(requests)

# 搜索
search_request = SearchMemoryRequest(
    tenant_id="tenant1",
    account_id="sales1",
    contact_id="customer1",
    latest_msg="客户反馈",
    type=MemType.ONLINE,
    mode=1
)
search_response = await stub.SearchMemory(search_request)
```

---

## 总结

**gRPC文件夹 = 网络接口层**

### 两个文件的角色

**salesmemory.proto**：
- 定义服务接口合约
- 定义消息结构
- 跨语言、版本兼容性保证

**memory_service.py**：
- 实现proto定义的服务
- 连接gRPC与业务逻辑
- 处理请求、路由、异常、响应

### 核心价值

1. **服务网关** — 所有记忆操作的唯一入口
2. **流程路由** — 根据类型选择不同处理流程
3. **批量优化** — 支持单个和批量操作
4. **异常处理** — 完整的错误管理和传递
5. **性能监控** — 完整的日志和耗时统计

### 整体位置

```
网络边界
    ↑
    ├─ MemoryService (memory_service.py)
    │  ├─ AddMemories → 批量处理
    │  ├─ AddMemory → 单个处理
    │  └─ SearchMemory → 搜索处理
    │
    ├─ 流程路由
    │  ├─ type=ACTIVATE → activatememoryflow
    │  └─ type=ONLINE → onlinememoryflow
    │
    └─ 业务逻辑
       ├─ Agents (提取、检索、冲突)
       ├─ Clients (DB、向量库、缓存)
       └─ Utils (工具函数)
```
