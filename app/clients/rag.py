#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Optional
import aiohttp

from app.config.logger_setup import logger
from app.config.setting import grpc_client_param
from app.clients.base import BaseClient
from app.utils.consul_utils import extract_ip_port, get_service


class RagClient(BaseClient):
    _instance: Optional['RagClient'] = None

    def __init__(self):
        self._semantic_mode = "semantic"
        self._table_mode = "table"
        rag_host_port = extract_ip_port(get_service(grpc_client_param.sales_rag_service_name))
        self._rag_url = f"http://{rag_host_port}/api/v1/activation/rag"
        self._client = None

    @classmethod
    def get_instance(cls) -> 'RagClient':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.connect()
        return cls._instance

    def connect(self) -> None:
        self._client = aiohttp.ClientSession()

    def close(self) -> None:
        self._client.close()
        self._instance = None

    def is_connected(self) -> bool:
        pass

    @property
    def rag(self) -> 'RagClient':
        return self

    def _check_param(self, tenant_id: str, database: str, mode: str, columns: list[str], params: dict = None):
        invalid_params_list = list()
        param_info = {"tenant_id": tenant_id, "database": database, "mode": mode, "columns": columns}
        for key, value in param_info.items():
            if not value:
                invalid_params_list.append(key)
        if invalid_params_list:
            raise Exception(f"参数{invalid_params_list}不能为空")
        if mode != self._semantic_mode and mode != self._table_mode:
            raise Exception(f"参数 mode 必须为 {self._semantic_mode} 或者 {self._table_mode}")

    async def search(self, tenant_id: str, mode: str, database: str, filters: list[dict], columns: list,
                     params: dict = None, page_index: int = 1, page_size: int = 20) -> dict:
        if not params:
            params = {}
        data = {
            "mode": mode, "database": database, "filters": filters, "columns": columns,
            "params": params, "tenant_id": tenant_id, "page_index": page_index, "page_size": page_size
        }
        self._check_param(tenant_id=data.get("tenant_id"), database=data.get("database"),
                          mode=data.get("mode"), columns=data.get("columns"), params=data.get("params"))
        response = await self._client.post(url=self._rag_url, json=data)
        if response.status != 200:
            logger.error(response.content)
            return {}
        return await response.json()
