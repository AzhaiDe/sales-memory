# Scheduler 文件夹架构分析

## 整体作用
**定时任务管理层** — 使用APScheduler框架实现定时删除过期记忆的后台任务。

---

## 文件1：base.py（单例元类）

### 主要职责
提供单例元类，确保类只有一个实例。

### Singleton 元类

```python
class Singleton(abc.ABCMeta, type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
```

**工作原理**：
- 继承ABCMeta和type，使其成为元类
- 重写__call__方法，在创建实例时进行拦截
- 第一次创建时，将实例存入_instances字典
- 后续创建时，直接返回已存储的实例

**使用方式**：
```python
class SchedulerTask(object, metaclass=Singleton):
    pass

# 无论创建多少次，返回的都是同一个实例
scheduler1 = SchedulerTask()
scheduler2 = SchedulerTask()
assert scheduler1 is scheduler2  # True
```

---

## 文件2：delete_expired_memory.py（过期记忆删除）

### 主要职责
实现过期记忆的检测和删除逻辑。

### 函数1：delete_schedule_task()

```python
def delete_schedule_task(delete_info: dict):
    """由APScheduler调用的任务入口"""
    asyncio.run(delete_expired_memory(delete_info, MemType.ONLINE))
```

**作用**：
- 是APScheduler直接调用的同步函数
- 使用asyncio.run()包装异步函数
- 仅删除ONLINE类型的过期记忆

---

### 函数2：delete_expired_memory()

**流程**：
```
1. 获取Milvus客户端
   milvus_client = await AsyncMilvusClient.get_instance().milvus
   
2. 获取内存类型后缀
   suffix = get_memory_type(memory_type)  # "_0" for ONLINE
   
3. 获取所有集合
   all_collections = await milvus_client.list_tenant_collections()
   
4. 筛选目标集合（按后缀）
   target_collections = [coll for coll in all_collections if coll.endswith(suffix)]
   
5. 提取租户IDs
   tenant_ids = [milvus_client.get_tenant_id_from_collection(coll, suffix) ...]
   
6. 并发处理每个租户
   tasks = [_process_tenant_expired_memory(...) for tenant_id in tenant_ids]
   results = await asyncio.gather(*tasks, return_exceptions=True)
   
7. 统计和日志
   total_deleted = sum(results)
   logger.info(f"总共删除{total_deleted}条")
```

**关键点**：
- 支持多租户并发删除
- 使用asyncio.gather()并发执行
- return_exceptions=True捕获异常，不中断其他任务

---

### 函数3：_process_tenant_expired_memory()

**单租户处理流程**：
```
1. 按category查询记忆
   search_result = await milvus_client.filter_search(
       tenant_id=tenant_id,
       category=category,
       suffix=suffix
   )
   
2. 遍历每条记忆
   for memory in search_result:
       now_time = int(datetime.now().timestamp())
       if memory.expire_time != 0 and memory.expire_time < now_time:
           delete_memory_list.append(memory.id)
   
3. 批量删除
   if delete_memory_list:
       await milvus_client.delete(
           tenant_id=tenant_id,
           ids=delete_memory_list,
           suffix=suffix
       )
   
4. 返回删除数量
   return len(delete_memory_list)
```

**核心逻辑**：
- expire_time == 0 表示永不过期
- expire_time < 当前时间 表示已过期
- 过期判断使用Unix时间戳比较

---

## 文件3：scheduler.py（定时任务管理）

### 主要职责
使用APScheduler框架管理定时任务的创建、启动和停止。

### SchedulerTask 类

**使用Singleton元类**：
```python
class SchedulerTask(object, metaclass=Singleton):
    pass
```

**确保整个应用只有一个调度器实例**

---

### 方法1：init_schedule()

**初始化APScheduler配置**：
```python
interval_task = {
    "executors": {
        'default': ThreadPoolExecutor(10)  # 最多10个线程
    },
    "job_defaults": {
        'coalesce': False,       # 不合并错过的执行
        'max_instances': 1       # 同一任务最多1个实例
    }
}
self.scheduler = BackgroundScheduler(**interval_task)
```

**配置说明**：
- ThreadPoolExecutor(10)：线程池最多10个线程
- coalesce=False：如果任务错过执行时间，不会合并执行
- max_instances=1：防止同一任务并发执行

---

### 方法2：add_scheduler_task()

**添加定时任务**：
```python
self.scheduler.add_job(
    delete_schedule_task,  # 执行的函数
    CronTrigger(
        hour=schedule_param.delete_expired_memory_trigger.get("hour"),
        minute=schedule_param.delete_expired_memory_trigger.get("minute")
    ),  # Cron表达式（每天指定时间）
    kwargs={"delete_info": schedule_param.delete_expired_memory_param}
)
```

**时间控制**：
- 从配置中读取hour和minute
- 每天指定时间执行
- 例：hour=0, minute=0 表示每天00:00执行

---

### 方法3：start()

```python
def start(self):
    self.init_schedule()
    self.add_scheduler_task()
    self.scheduler.start()
```

**启动流程**：
1. 初始化APScheduler
2. 添加删除过期记忆任务
3. 启动后台调度器

---

### 方法4：stop()

```python
def stop(self):
    self.scheduler.shutdown()
```

**停止调度器并释放资源**

---

## 三个文件的协作流程

```
base.py (Singleton元类)
    ↓ (提供单例保证)
    
scheduler.py (SchedulerTask)
    ├→ init_schedule()
    │  └→ 创建BackgroundScheduler
    ├→ add_scheduler_task()
    │  └→ 添加删除任务到调度器
    ├→ start()
    │  └→ 启动后台调度器
    └→ stop()
       └→ 停止调度器

                ↓
            delete_expired_memory.py
            ├→ delete_schedule_task()
            │  入口函数（同步）
            ├→ delete_expired_memory()
            │  并发处理所有租户
            └→ _process_tenant_expired_memory()
               处理单个租户的过期记忆

                ↓
            Milvus向量数据库
            └→ 删除过期的记忆数据
```

---

## 整体工作流程

### 应用启动时

```
应用启动
    ↓
SchedulerTask().start()
    ├→ 初始化APScheduler
    ├→ 添加定时任务（每天指定时间）
    └→ 启动后台调度器
    ↓
后台开始运行
```

### 定时执行

```
每天 delete_expired_memory_trigger.hour:minute
    ↓
APScheduler触发
    ↓
delete_schedule_task()
    ↓
asyncio.run(delete_expired_memory(...))
    ├→ 获取所有租户集合
    ├→ 并发处理每个租户
    │  ├→ 查询过期记忆
    │  └→ 批量删除
    └→ 日志统计
```

---

## 设计特点

| 特性 | 实现 | 优势 |
|------|------|------|
| **后台运行** | BackgroundScheduler | 不阻塞主应用线程 |
| **单例管理** | Singleton元类 | 整个应用只有一个调度器 |
| **多租户并发** | asyncio.gather() | 并发删除，提高效率 |
| **异常隔离** | return_exceptions=True | 一个租户失败不影响其他 |
| **线程池** | ThreadPoolExecutor(10) | 可配置的并发能力 |
| **Cron表达式** | CronTrigger | 灵活的时间控制 |
| **过期判断** | timestamp比较 | 精确的过期检测 |

---

## 总结

**Scheduler文件夹 = 后台定时任务管理**

### 三个文件的角色

**base.py**：
- 提供Singleton元类
- 确保单例实例

**scheduler.py**：
- 使用APScheduler框架
- 管理任务的生命周期

**delete_expired_memory.py**：
- 实现过期记忆删除逻辑
- 支持多租户并发处理

### 核心价值

1. **自动化** — 定时自动删除过期记忆
2. **资源管理** — 释放过期数据占用的存储空间
3. **性能优化** — 清理冗余数据，提高查询性能
4. **高效率** — 多租户并发执行
5. **可靠性** — 异常隔离，一个租户失败不影响其他

### 使用示例

```python
# 应用启动时
scheduler_task = SchedulerTask()
scheduler_task.start()

# 应用关闭时
scheduler_task.stop()
```

### 配置示例

```python
# 在config.setting中
schedule_param.delete_expired_memory_trigger = {
    "hour": 0,    # 每天0点
    "minute": 0   # 0分
}

schedule_param.delete_expired_memory_param = {
    "近期情况": {
        "行程安排": 7,    # 7天后过期
        "健康情况": 7     # 7天后过期
    }
}
```
