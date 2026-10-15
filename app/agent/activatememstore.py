#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import time

from autogen_core import type_subscription, message_handler, MessageContext, DefaultTopicId

from app.agent.base import BaseAgent
from app.clients.embedding import EmbeddingClient
from app.config.logger_setup import logger
from app.enums.agent_topic import TopicType
from app.exceptions.custom import AgentMemoryException
from app.grpc.proto.internal.salesmemory_pb2 import SearchMemoryRequest, Memory
from app.schemas.body import AddMemoryAgent, AddMemoryResult, SearchMemoryResult
from app.schemas.milvus_schemas import MemorySchemaData
from app.utils.common_utils import get_memory_type

embedding_client = EmbeddingClient()


def _build_milvus_body(message: AddMemoryAgent, content: str) -> list[MemorySchemaData]:
    logger.debug(f"build raw milvus body, content={content}")
    json_content = json.loads(content)

    cur_time = int(time.time())
    data: list[MemorySchemaData] = list()
    for category, entry in json_content.items():
        for theme, items in entry.items():
            if isinstance(items, dict):
                facts: list[str] = [json.dumps({key: value}, ensure_ascii=False) for key, value in items.items()]
            else:
                facts: list[str] = [str(items)]

            schema_data: MemorySchemaData = MemorySchemaData(
                tenant_id=message.tenant_id,
                account_id=message.account_id,
                contact_id=message.contact_id,
                category=category,
                theme=theme,
                fact=facts,
                history=[json.dumps({"action": "add"}, ensure_ascii=False)],
                occur_time=cur_time,
                expire_time=cur_time,
                update_time=cur_time,
                theme_vector=embedding_client.get_embeddings([theme])[0],
                fact_vector=embedding_client.get_embeddings([";".join(facts)])[0],
            )
            data.append(schema_data)
    return data


@type_subscription(topic_type=TopicType.ACTIVATE_MEM_STORE.value)
class ActivateMemStore(BaseAgent):
    """ActivateMemAgent 提取记忆体事实"""

    def __init__(self):
        super().__init__("用于提取记忆体事实的agent")

    @message_handler
    @BaseAgent.trace_performance
    @BaseAgent.handle_exceptions
    async def handle_save_memory(self, message: AddMemoryAgent, ctx: MessageContext) -> None:
        await self.get_milvus_client()

        async def upsert(data: list[MemorySchemaData]):
            filter_res: list[dict] = await self._milvus_client.filter_search(tenant_id=message.tenant_id,
                                                                             account_id=message.account_id,
                                                                             contact_id=message.contact_id,
                                                                             suffix=message.type)
            logger.info(
                f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
                f"contact_id={message.contact_id}, milvus will delete old memory")
            ids: list = [item["id"] for item in filter_res]
            if len(ids) != 0:
                delete_res: bool = await self._milvus_client.delete(message.tenant_id, ids, message.type)
                if not delete_res:
                    logger.error("Milvus delete failed, ids=", ids)
                    return delete_res

            logger.info(
                f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
                f"contact_id={message.contact_id}, milvus will insert new memory")

            insert_res: bool = await self._milvus_client.insert(message.tenant_id,
                                                                [record.to_dict() for record in data], message.type)
            if not insert_res:
                logger.error("Milvus insert failed, data=", data)

            return insert_res

        data: list[MemorySchemaData] = _build_milvus_body(message, message.context)
        if len(data) == 0 or not await upsert(data):
            logger.error(
                f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
                f"contact_id={message.contact_id}, milvus upsert failed, milvus content={data}"
            )
            raise AgentMemoryException(message=f"activate memory store failed, the content are {data}")

        memories: list[Memory] = [
            Memory(id=idx, category=data[idx].category, theme=data[idx].theme, fact=data[idx].fact)
            for idx in range(len(data))
        ]

        await self.publish_message(AddMemoryResult(memory=memories), DefaultTopicId())

    @message_handler
    @BaseAgent.trace_performance
    @BaseAgent.handle_exceptions
    async def handle_search_memory(self, message: SearchMemoryRequest, ctx: MessageContext) -> None:
        await self.get_milvus_client()
        memory_type = get_memory_type(message.type)

        data: list[dict] = await self._milvus_client.filter_search(tenant_id=message.tenant_id,
                                                                   account_id=message.account_id,
                                                                   contact_id=message.contact_id,
                                                                   suffix=memory_type)

        memories: list[Memory] = [
            Memory(id=memory.get("id"), category=memory.get("category"), theme=memory.get("theme"),
                   fact=memory.get("fact"))
            for memory in data
        ]

        await self.publish_message(SearchMemoryResult(memory=memories), DefaultTopicId())
