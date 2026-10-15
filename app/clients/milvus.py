#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
import json
from time import time
from typing import Optional, List, Dict, Any

from app.config.logger_setup import logger
from pymilvus import connections, Collection, utility, MilvusException

from app.clients.base import BaseClient
from app.config.setting import milvus_param
from app.schemas.milvus_schemas import get_memory_schema


class MilvusClient(BaseClient):
    _instance: Optional['MilvusClient'] = None

    def __init__(self):
        super().__init__()
        self._connected = False
        self._collections: Dict[str, Collection] =

    @classmethod
    def get_instance(cls) -> 'MilvusClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_collection_name(self, tenant_id: str, suffix: str = "") -> str:
        return f"{milvus_param.milvus_collection_prefix}{tenant_id}{suffix}"

    def connect(self) -> None:
        try:
            connections.connect(alias="default", host=milvus_param.milvus_host, port=milvus_param.milvus_port,
                                user=milvus_param.milvus_user, password=milvus_param.milvus_password,
                                db_name=milvus_param.milvus_database)
            self._connected = True
            self._client = connections
            logger.info(f"Milvus连接成功: {milvus_param.milvus_host}:{milvus_param.milvus_port}")
        except MilvusException as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            raise

    def close(self) -> None:
        if self._connected:
            for collection_name, collection in self._collections.items():
                try:
                    collection.release()
                except Exception as e:
                    logger.warning(f"释放集合 {collection_name} 失败: {str(e)}")
            self._collections.clear()
            connections.disconnect("default")
            self._connected = False
            self._client = None

    def is_connected(self) -> bool:
        return self._connected

    @property
    def milvus(self) -> 'MilvusClient':
        if not self.is_connected():
            self.connect()
        return self

    def _ensure_collection_exists(self, tenant_id: str, suffix: str = "") -> Collection:
        collection_name = self._get_collection_name(tenant_id, suffix)
        if collection_name in self._collections:
            return self._collections[collection_name]
        if not utility.has_collection(collection_name):
            return self._create_collection(tenant_id, suffix)
        try:
            collection = Collection(name=collection_name, using="default")
            collection.load()
            self._collections[collection_name] = collection
            return collection
        except MilvusException as e:
            logger.error(f"加载集合 {collection_name} 失败: {str(e)}")
            raise

    def _create_collection(self, tenant_id: str, suffix: str = "") -> Collection:
        collection_name = self._get_collection_name(tenant_id, suffix)
        try:
            schema = get_memory_schema()
            collection = Collection(name=collection_name, schema=schema, using="default")
            collection.create_index(field_name="theme_vector",
                                    index_params={"metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 8, "efConstruction": 64}})
            collection.create_index(field_name="fact_vector",
                                    index_params={"metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 8, "efConstruction": 64}})
            for field in ["tenant_id", "account_id", "contact_id", "category", "theme"]:
                collection.create_index(field_name=field, index_params={"index_type": "INVERTED"})
            collection.load()
            self._collections[collection_name] = collection
            logger.info(f"成功为租户 {tenant_id} 创建集合: {collection_name}")
            return collection
        except MilvusException as e:
            logger.error(f"为租户 {tenant_id} 创建集合失败: {str(e)}")
            raise

    def list_tenant_collections(self) -> List[str]:
        all_collections = utility.list_collections()
        return [c for c in all_collections if c.startswith(milvus_param.milvus_collection_prefix)]

    def get_tenant_id_from_collection(self, collection_name: str) -> Optional[str]:
        if collection_name.startswith(milvus_param.milvus_collection_prefix):
            return collection_name[len(milvus_param.milvus_collection_prefix):]
        return None

    def insert(self, tenant_id: str, data: List, suffix: str = "") -> List[int]:
        try:
            collection = self._ensure_collection_exists(tenant_id, suffix)
            result = collection.insert(data)
            collection.flush()
            ids = result.primary_keys
            logger.info(f"成功插入记录: 租户={tenant_id}, 记录数={len(data)}, IDs={ids}")
            return ids
        except MilvusException as e:
            logger.error(f"插入记录失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    def upsert(self, tenant_id: str, data: List, suffix: str = "") -> bool:
        try:
            collection = self._ensure_collection_exists(tenant_id, suffix)
            collection.upsert(data)
            collection.flush()
            logger.info(f"成功插入记录: 租户={tenant_id}, data={data}")
            return True
        except MilvusException as e:
            logger.error(f"插入记录失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    def delete(self, tenant_id: str, ids: List[str], suffix: str = "") -> bool:
        if not ids:
            return False
        try:
            collection = self._ensure_collection_exists(tenant_id, suffix)
            id_list_str = ", ".join([f"{id}" for id in ids])
            result = collection.delete(f"id in [{id_list_str}]")
            deleted_count = result.delete_count
            logger.info(f"批量删除记录: 租户={tenant_id}, ID数量={len(ids)}, 实际删除数量={deleted_count}")
            return deleted_count > 0
        except MilvusException as e:
            logger.error(f"批量删除记录失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    def filter_search(self, tenant_id: str, account_id: str = None, contact_id: str = None,
                      category: Optional[str] = None, theme: Optional[str] = None,
                      limit: int = 100, offset: int = 0, suffix: str = "") -> List[Dict[str, Any]]:
        try:
            collection = self._ensure_collection_exists(tenant_id, suffix)
            conditions = []
            if account_id:
                conditions.append(f"account_id == '{account_id}'")
            if contact_id:
                conditions.append(f"contact_id == '{contact_id}'")
            if category:
                conditions.append(f"category like '%{category}%'")
            if theme:
                conditions.append(f"theme like '%{theme}%'")
            expr = " and ".join(conditions) if conditions else ""
            return collection.query(expr=expr, output_fields=["*"], limit=limit, offset=offset)
        except MilvusException as e:
            logger.error(f"过滤查询失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    def vector_search(self, tenant_id: str, account_id: str, contact_id: str, vector: List[List[float]],
                      category: Optional[str] = None, theme: Optional[str] = None,
                      field_name: str = "fact_vector", top_k: int = 5, suffix: str = "") -> List[Dict[str, Any]]:
        try:
            collection = self._ensure_collection_exists(tenant_id, suffix)
            conditions = []
            if account_id:
                conditions.append(f"account_id == '{account_id}'")
            if contact_id:
                conditions.append(f"contact_id == '{contact_id}'")
            if category:
                conditions.append(f"category like '%{category}%'")
            if theme:
                conditions.append(f"theme like '%{theme}%'")
            expr = " and ".join(conditions) if conditions else None
            return collection.search(data=vector, anns_field=field_name,
                                     param={"metric_type": "COSINE", "params": {"ef": 64}},
                                     limit=top_k, expr=expr, output_fields=["*"])
        except MilvusException as e:
            logger.error(f"向量搜索失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    def drop_collection(self, tenant_id: str, suffix: str = "") -> bool:
        collection_name = self._get_collection_name(tenant_id, suffix)
        try:
            if collection_name in self._collections:
                self._collections[collection_name].release()
                del self._collections[collection_name]
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
                return True
            return False
        except MilvusException as e:
            logger.error(f"删除租户 {tenant_id} 的集合失败: {str(e)}")
            raise


class AsyncMilvusClient(BaseClient):
    _instance: Optional['AsyncMilvusClient'] = None

    def __init__(self):
        super().__init__()
        self._connected = False
        self._collections: Dict[str, Collection] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'AsyncMilvusClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_collection_name(self, tenant_id: str, suffix: str = "") -> str:
        return f"{milvus_param.milvus_collection_prefix}{tenant_id}{suffix}"

    async def connect(self) -> None:
        async with self._lock:
            if not self._connected:
                try:
                    await asyncio.to_thread(connections.connect, alias="default",
                                            host=milvus_param.milvus_host, port=milvus_param.milvus_port,
                                            user=milvus_param.milvus_user, password=milvus_param.milvus_password,
                                            db_name=milvus_param.milvus_database, pool_size=milvus_param.milvus_pool_size)
                    self._connected = True
                    self._client = connections
                except MilvusException as e:
                    logger.error(f"Milvus异步连接失败: {str(e)}")
                    raise

    async def close(self) -> None:
        async with self._lock:
            if self._connected:
                for collection_name, collection in self._collections.items():
                    try:
                        await asyncio.to_thread(collection.release)
                    except Exception as e:
                        logger.warning(f"释放集合 {collection_name} 失败: {str(e)}")
                self._collections.clear()
                await asyncio.to_thread(connections.disconnect, "default")
                self._connected = False
                self._client = None

    def is_connected(self) -> bool:
        return self._connected

    @property
    async def milvus(self) -> 'AsyncMilvusClient':
        if not self.is_connected():
            await self.connect()
        return self

    async def _ensure_collection_exists(self, tenant_id: str, suffix: str = "") -> Collection:
        collection_name = self._get_collection_name(tenant_id, suffix)
        if collection_name in self._collections:
            return self._collections[collection_name]
        async with self._lock:
            if collection_name in self._collections:
                return self._collections[collection_name]
            has_collection = await asyncio.to_thread(utility.has_collection, collection_name)
            if not has_collection:
                return await self._create_collection(tenant_id, suffix)
            try:
                collection = await asyncio.to_thread(lambda: Collection(name=collection_name, using="default"))
                await asyncio.to_thread(collection.load)
                self._collections[collection_name] = collection
                return collection
            except MilvusException as e:
                logger.error(f"加载集合 {collection_name} 失败: {str(e)}")
                raise

    async def _create_collection(self, tenant_id: str, suffix: str = "") -> Collection:
        collection_name = self._get_collection_name(tenant_id, suffix)
        try:
            schema = get_memory_schema()
            collection = await asyncio.to_thread(lambda: Collection(name=collection_name, schema=schema, using="default"))
            await asyncio.to_thread(collection.create_index, field_name="theme_vector",
                                    index_params={"metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 16, "efConstruction": 64}})
            await asyncio.to_thread(collection.create_index, field_name="fact_vector",
                                    index_params={"metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 16, "efConstruction": 64}})
            for field in ["tenant_id", "account_id", "contact_id", "category", "theme"]:
                await asyncio.to_thread(collection.create_index, field_name=field,
                                        index_params={"index_type": "INVERTED"})
            await asyncio.to_thread(collection.load)
            self._collections[collection_name] = collection
            logger.info(f"成功为租户 {tenant_id} 创建集合: {collection_name}")
            return collection
        except MilvusException as e:
            logger.error(f"为租户 {tenant_id} 创建集合失败: {str(e)}")
            raise

    async def list_tenant_collections(self) -> List[str]:
        all_collections = await asyncio.to_thread(utility.list_collections)
        return [c for c in all_collections if c.startswith(milvus_param.milvus_collection_prefix)]

    def get_tenant_id_from_collection(self, collection_name: str, suffix: str = "") -> Optional[str]:
        if collection_name.startswith(milvus_param.milvus_collection_prefix):
            tenant_id = collection_name[len(milvus_param.milvus_collection_prefix):]
            if suffix and tenant_id.endswith(suffix):
                tenant_id = tenant_id[:-len(suffix)]
            return tenant_id
        return None

    @BaseClient.trace_performance
    async def insert(self, tenant_id: str, data: List, suffix: str = "") -> List[int]:
        try:
            collection = await self._ensure_collection_exists(tenant_id, suffix)
            result = await asyncio.to_thread(collection.insert, data)
            await asyncio.to_thread(collection.flush)
            ids = result.primary_keys
            logger.info(f"成功插入记录: 租户={tenant_id}, 记录数={len(data)}, IDs={ids}")
            return ids
        except MilvusException as e:
            logger.error(f"插入记录失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    @BaseClient.trace_performance
    async def delete(self, tenant_id: str, ids: List[str], suffix: str = "") -> bool:
        if not ids:
            return False
        try:
            collection = await self._ensure_collection_exists(tenant_id, suffix)
            id_list_str = ", ".join([f"{id}" for id in ids])
            result = await asyncio.to_thread(collection.delete, f"id in [{id_list_str}]")
            deleted_count = result.delete_count
            logger.info(f"批量删除记录: 租户={tenant_id}, ID数量={len(ids)}, 实际删除数量={deleted_count}")
            return deleted_count > 0
        except MilvusException as e:
            logger.error(f"批量删除记录失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    @BaseClient.trace_performance
    async def filter_search(self, tenant_id: str, account_id: str = None, contact_id: str = None,
                            category: Optional[str] = None, theme: Optional[str] = None,
                            limit: int = 100, offset: int = 0, output_fields: List[str] = ['*'],
                            suffix: str = "") -> List[Dict[str, Any]]:
        try:
            collection = await self._ensure_collection_exists(tenant_id, suffix)
            conditions = []
            if account_id:
                conditions.append(f"account_id == '{account_id}'")
            if contact_id:
                conditions.append(f"contact_id == '{contact_id}'")
            if category:
                conditions.append(f"category like '%{category}%'")
            if theme:
                conditions.append(f"theme like '%{theme}%'")
            expr = " and ".join(conditions) if conditions else ""
            return await asyncio.to_thread(collection.query, expr=expr, output_fields=output_fields,
                                           limit=limit, offset=offset)
        except MilvusException as e:
            logger.error(f"过滤查询失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    @BaseClient.trace_performance
    async def vector_search(self, tenant_id: str, account_id: str, contact_id: str,
                            vector: List[List[float]], category: Optional[str] = None, theme: Optional[str] = None,
                            field_name: str = "fact_vector", top_k: int = 5,
                            output_fields: List[str] = ['*'], suffix: str = "") -> List[Dict[str, Any]]:
        try:
            collection = await self._ensure_collection_exists(tenant_id, suffix)
            conditions = []
            if account_id:
                conditions.append(f"account_id == '{account_id}'")
            if contact_id:
                conditions.append(f"contact_id == '{contact_id}'")
            if category:
                conditions.append(f"category like '%{category}%'")
            if theme:
                conditions.append(f"theme like '%{theme}%'")
            expr = " and ".join(conditions) if conditions else None
            search_params = {"metric_type": "COSINE", "params": {"ef": 16}}
            result = await asyncio.to_thread(collection.search, data=vector, anns_field=field_name,
                                             param=search_params, limit=top_k, expr=expr, output_fields=output_fields)
            return result
        except MilvusException as e:
            logger.error(f"向量搜索失败: 租户={tenant_id}, 错误={str(e)}")
            raise

    @BaseClient.trace_performance
    async def drop_collection(self, tenant_id: str, suffix: str = "") -> bool:
        collection_name = self._get_collection_name(tenant_id, suffix)
        try:
            async with self._lock:
                if collection_name in self._collections:
                    await asyncio.to_thread(self._collections[collection_name].release)
                    del self._collections[collection_name]
                has_collection = await asyncio.to_thread(utility.has_collection, collection_name)
                if has_collection:
                    await asyncio.to_thread(utility.drop_collection, collection_name)
                    return True
                return False
        except MilvusException as e:
            logger.error(f"删除租户 {tenant_id} 的集合失败: {str(e)}")
            raise
