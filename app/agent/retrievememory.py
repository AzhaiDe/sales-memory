#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import traceback

from autogen_core import type_subscription, message_handler, MessageContext, TopicId, DefaultTopicId
from autogen_core.models import CreateResult
from json_repair import repair_json

from app.agent.base import BaseAgent
from app.clients.embedding import EmbeddingClient
from app.config.logger_setup import logger
from app.config.setting import test_param
from app.enums.agent_topic import TopicType
from app.enums.prompt_types import PromptType
from app.grpc.proto.internal.salesmemory_pb2 import SearchMemoryRequest
from app.models.factory import ModelClientFactory
from app.schemas.body import AddMemoryAgent, MemoryAgent, SearchMemoryResult
from app.schemas.prompt_data import RewriteQueryData
from app.utils.common_utils import prompt_log, get_memory_type
from app.utils.context_utils import ContextUtil
from app.utils.excel_utils import ExcelUtils


@type_subscription(topic_type=TopicType.RETRIEVE_MEMORY_AGENT.value)
class RetrieveMemoryAgent(BaseAgent):
    """Retrieve Memory Agent，检索记忆"""

    def __init__(self):
        super().__init__("用于检索记忆的agent")
        self._model_client = ModelClientFactory.get_default_client()
        self._embedding_client = EmbeddingClient()
        self._excel_util = ExcelUtils()

    @message_handler
    @BaseAgent.handle_exceptions
    @BaseAgent.trace_performance
    async def handle_add_memory(self, message: AddMemoryAgent, ctx: MessageContext) -> None:
        await self.get_milvus_client()
        fact_list = []
        for item in message.fact:
            if item.get("fact", None) is not None:
                merge_facts = ""
                for fact in item.get("fact", []):
                    merge_facts += fact + ";"
                fact_list.append(merge_facts)

        merge_memory_dict = {}
        merge_memory_dict = await self.search_old_memory(message, fact_list, merge_memory_dict, "fact_vector", 3)

        retrieve_memory_ids = []
        retrieve_memory_list = []
        for memory_id, memory_value in merge_memory_dict.items():
            retrieve_memory_ids.append(memory_id)
            retrieve_memory_list.append(memory_value)

        message.old_memory = retrieve_memory_list
        logger.info(f"[SEARCH_RESULT][ADD_MEMORY] retrieve memory by vector: {retrieve_memory_ids}, "
                    f"tenant_id={message.tenant_id}, account_id={message.account_id}, contact_id={message.contact_id}")
        await self.publish_message(message,
                                   topic_id=TopicId(TopicType.RESOLVE_CONFLICT_AGENT.value, source=self.id.key))

    @message_handler
    @BaseAgent.handle_exceptions
    @BaseAgent.trace_performance
    async def handle_search_memory(self, message: SearchMemoryRequest, ctx: MessageContext) -> None:
        rewrite_query = ""
        final_result = []
        memory_type = get_memory_type(message.type)
        await self.get_milvus_client()

        if not message.mode:
            search_result = await self._milvus_client.filter_search(tenant_id=message.tenant_id,
                                                                    account_id=message.account_id,
                                                                    contact_id=message.contact_id,
                                                                    output_fields=["id", "theme", "fact", "occur_time"],
                                                                    suffix=memory_type)
            for memory in search_result:
                final_result.append({"id": memory.get("id"), "category": "", "theme": memory.get("theme"),
                                     "fact": memory.get("fact"), "occur_time": memory.get("occur_time")})
            logger.info(f"[SEARCH_RESULT][SEARCH_MEMORY] condition search result: {final_result}, "
                        f"tenant_id={message.tenant_id}, account_id={message.account_id}, contact_id={message.contact_id}")
        else:
            merge_memory_dict = {}
            memory_param = MemoryAgent(
                tenant_id=message.tenant_id, account_id=message.account_id,
                contact_id=message.contact_id, type=memory_type
            )
            rewrite_query = await self._get_rewrite_query(message, ctx)
            theme = message.theme if message.theme else rewrite_query.get("theme", "")
            merge_memory_dict = await self.search_old_memory(memory_agent=memory_param, search_value=[theme],
                                                             merge_memory_dict=merge_memory_dict,
                                                             field_name="theme_vector", top_k=3,
                                                             category=message.category, theme=message.theme)
            merge_memory_dict = await self.search_old_memory(memory_agent=memory_param,
                                                             search_value=[rewrite_query.get("query", "")],
                                                             merge_memory_dict=merge_memory_dict,
                                                             field_name="fact_vector", top_k=3,
                                                             category=message.category, theme=message.theme)
            for memory in merge_memory_dict.values():
                final_result.append({"id": memory.get("id"), "category": "", "theme": memory.get("theme"),
                                     "fact": memory.get("fact"), "occur_time": memory.get("occur_time")})
            logger.info(f"[SEARCH_RESULT][SEARCH_MEMORY] vector search result: {final_result}, "
                        f"tenant_id={message.tenant_id}, account_id={message.account_id}, contact_id={message.contact_id}")

        if test_param.test_enable:
            export_result = {
                "tenant_id": message.tenant_id, "account_id": message.account_id,
                "contact_id": message.contact_id, "mode": message.mode,
                "rewrite_query": rewrite_query, "search_result": final_result
            }
            self._excel_util.export_result(result=export_result, sheet_name="search_memory")
        await self.publish_message(SearchMemoryResult(memory=final_result), DefaultTopicId())

    async def search_old_memory(self, memory_agent: MemoryAgent, search_value: list, merge_memory_dict: dict,
                                field_name: str, top_k: int, category: str = None, theme: str = None):
        vector_list = self._embedding_client.get_embeddings(search_value)
        vector_search_result = await self._milvus_client.vector_search(
            tenant_id=memory_agent.tenant_id, account_id=memory_agent.account_id,
            contact_id=memory_agent.contact_id, category=category, theme=theme,
            vector=vector_list, field_name=field_name, top_k=top_k,
            output_fields=["id", "theme", "fact", "occur_time", "history"],
            suffix=memory_agent.type,
        )
        for search_result in vector_search_result:
            for item in search_result:
                old_memory = item.entity.fields
                memory_id = old_memory.get("id")
                merge_memory_dict[memory_id] = old_memory
        return merge_memory_dict

    async def _get_rewrite_query(self, message: SearchMemoryRequest, ctx: MessageContext):
        ctx_utils = ContextUtil(message.contexts)
        context = ctx_utils.get_context_with_timestamp()
        synopsis = RewriteQueryData(context=context, latest_msg=message.latest_msg)
        prompt = self.get_prompt(message.tenant_id, PromptType.REWRITE_QUERY.value, synopsis.to_dict())
        logger.debug(prompt_log(task_name=PromptType.REWRITE_QUERY.value, tenant_id=message.tenant_id,
                                account_id=message.account_id, contact_id=message.contact_id, prompt=prompt))
        try:
            rewrite_query_result: CreateResult = await self.create(self._model_client, prompt, ctx)
            logger.info(f'[PROMPT_RESULT][REWRITE_QUERY] rewrite query result content: {rewrite_query_result.content}, '
                        f'tenant_id={message.tenant_id}, account_id={message.account_id}, contact_id={message.contact_id}')
            content = rewrite_query_result.content if rewrite_query_result else '{}'
            final_result = json.loads(repair_json(content, ensure_ascii=False))
        except Exception as e:
            logger.error(f'rewrite query error: {e}, tenant_id={message.tenant_id}, '
                         f'account_id={message.account_id}, contact_id={message.contact_id}')
            logger.debug(f'rewrite query error stack: {traceback.format_exc()}')
            final_result = {}
        return final_result
