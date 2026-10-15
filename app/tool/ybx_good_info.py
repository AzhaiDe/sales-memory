#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Annotated
from app.clients.factory import ClientFactory
from app.config.logger_setup import logger


async def get_good_info_ybx(sku_id: str, tenant_id: str = "ybx", good_name: str = "商品信息") -> Annotated[dict, "商品详细信息"]:
    client = ClientFactory.get_rag_client()
    filters: list[dict] = [{"type": "equal", "condition": {"子规格条码": [sku_id]}}]
    columns: list = ["消耗预估", "所属分类", "品牌", "适用月龄", "适用症状", "子规格名称", "子规格条码"]
    response: dict = await client.search(tenant_id, "table", good_name, filters, columns)
    good_info: dict = {}
    if response.get("code") != 200:
        logger.warning(f"get_good_info_ybx, response code={response.get('code')}, message={response.get('message', '')}")
    else:
        good_infos = response.get("data", [])
        if len(good_infos) >= 1:
            good_info = good_infos[0]
    return {
        'sku_id': sku_id, '子规格名称': good_info.get("子规格名称", ""), '分类': good_info.get("所述分类", ""),
        '品牌': good_info.get('品牌', ""), '适用月龄': good_info.get('适用月龄', ""),
        '单件消耗': good_info.get('消耗预估', ""), '适用症状': good_info.get('适用症状', ""),
    }
