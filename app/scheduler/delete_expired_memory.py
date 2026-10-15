#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
from datetime import datetime

from app.config.logger_setup import logger
from app.clients.milvus import AsyncMilvusClient
from app.enums.mem_types import MemType
from app.utils.common_utils import get_memory_type


def delete_schedule_task(delete_info: dict):
    logger.info(f"[Schedule Task] 开始删除过期记忆")
    asyncio.run(delete_expired_memory(delete_info, MemType.ONLINE))


async def delete_expired_memory(delete_info: dict, memory_type: int):
    milvus_client = await AsyncMilvusClient.get_instance().milvus
    suffix = get_memory_type(memory_type)
    all_collections = await milvus_client.list_tenant_collections()
    target_collections = [coll for coll in all_collections if coll.endswith(suffix)]

    if not target_collections:
        logger.info(f"没有找到带有'{suffix}'后缀的集合，跳过删除过期记忆任务")
        return

    tenant_ids = [milvus_client.get_tenant_id_from_collection(coll, suffix) for coll in target_collections]
    tasks = [_process_tenant_expired_memory(milvus_client, tenant_id, delete_info, suffix) for tenant_id in tenant_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_deleted = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"[Schedule Task] 处理租户 {tenant_ids[i]} 过期记忆时发生错误: {str(result)}")
        else:
            total_deleted += result
    logger.info(f"[Schedule Task] 总共删除 {total_deleted} 条过期记忆")


async def _process_tenant_expired_memory(milvus_client, tenant_id: str, delete_info: dict, suffix: str) -> int:
    delete_memory_list = []
    try:
        for category in delete_info:
            search_memory_result = await milvus_client.filter_search(tenant_id=tenant_id, category=category, suffix=suffix)
            for memory in search_memory_result:
                now_date = int(datetime.now().timestamp())
                if memory.get("expire_time") != 0 and memory.get("expire_time") < now_date:
                    delete_memory_list.append(memory.get("id"))
        if delete_memory_list:
            await milvus_client.delete(tenant_id=tenant_id, ids=delete_memory_list, suffix=suffix)
            logger.info(f"[Schedule Task] 租户 {tenant_id} 成功删除过期记忆：{len(delete_memory_list)} 条")
        return len(delete_memory_list)
    except Exception as e:
        logger.error(f"[Schedule Task] 处理租户 {tenant_id} 的过期记忆时发生错误: {str(e)}")
        return 0
