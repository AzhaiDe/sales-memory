#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Annotated
from app.clients.factory import ClientFactory
from app.config.logger_setup import logger


async def get_order_info_ybx(contact_id: str, tenant_id: str = "ybx", order_name: str = "订单信息") -> Annotated[list, "联系人订单信息"]:
    client = ClientFactory.get_rag_client()
    filters: list[dict] = [{"type": "equal", "condition": {"客户ID": [contact_id]}}]
    columns: list = ["销售单号", "商品ID", "商品名称", "成交金额", "商品成交数量", "成交时间"]
    order_info: dict = await client.search(tenant_id, "table", order_name, filters, columns)
    if order_info.get("code") != 200:
        logger.warning(f"get_order_info_ybx, response code={order_info.get('code')}, message={order_info.get('message', '')}")
        return []
    return order_info.get("data", [])
