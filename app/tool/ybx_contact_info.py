#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Annotated
from app.clients.factory import ClientFactory
from app.config.logger_setup import logger


async def get_contact_info_ybx(contact_id: str, tenant_id: str = "ybx", contact_name: str = "客户信息") -> Annotated[dict, "联系人信息"]:
    client = ClientFactory.get_rag_client()
    filters: list[dict] = [{"type": "equal", "condition": {"WID": [contact_id]}}]
    columns: list = ["会员姓名", "性别", "最小宝宝生日", "累计消费金额", "累计购买次数", "平均客单价", "是否超级会员", "会员剩余积分"]
    response: list = await client.search(tenant_id, "table", contact_name, filters, columns)
    contact_info: dict = {}
    if response.get("code") != 200:
        logger.warning(f"get_contact_info_ybx, response code={response.get('code')}, message={response.get('message', '')}")
    else:
        contact_infos = response.get("data", [])
        if len(contact_infos) >= 1:
            contact_info = contact_infos[0]
    return {
        "会员姓名": contact_info.get("会员姓名", None), "性别": contact_info.get("性别", None),
        "最小宝宝生日": contact_info.get("最小宝宝生日", None), "累计消费金额": contact_info.get("累计消费金额", None),
        "累计购买次数": contact_info.get("累计购买次数", None), "平均客单价": contact_info.get("平均客单价", None),
        "是否超级会员": contact_info.get("是否超级会员", None), "会员剩余积分": contact_info.get("会员剩余积分", None)
    }
