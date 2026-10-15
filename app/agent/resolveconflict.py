#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import time
import traceback
from typing import Optional, Dict

from autogen_core import type_subscription, message_handler, MessageContext, DefaultTopicId
from autogen_core.models import CreateResult
from json_repair import repair_json

from app.agent.base import BaseAgent
from app.clients.embedding import EmbeddingClient
from app.config.logger_setup import logger
from app.config.setting import schedule_param, test_param
from app.enums.agent_topic import TopicType
from app.enums.mem_types import ActionType
from app.enums.prompt_types import PromptType
from app.models.factory import ModelClientFactory
from app.schemas.body import AddMemoryAgent, AddMemoryResult
from app.schemas.milvus_schemas import MemorySchemaData
from app.schemas.prompt_data import ResolveConflictData
from app.utils.common_utils import prompt_log
from app.utils.excel_utils import ExcelUtils


@type_subscription(topic_type=TopicType.RESOLVE_CONFLICT_AGENT.value)
class ResolveConflictAgent(BaseAgent):
    """Resolve Conflict Agent，解决新旧记忆冲突"""

    def __init__(self):
        super().__init__("用于解决新旧记忆冲突的agent")
        self._model_client = ModelClientFactory.get_default_client()
        self._embedding_client = EmbeddingClient()
        self._excel_util = ExcelUtils()
        self._old_memory = []

    @message_handler
    @BaseAgent.handle_exceptions
    @BaseAgent.trace_performance
    async def handle_add_memory(self, message: AddMemoryAgent, ctx: MessageContext) -> None:
        await self.get_milvus_client()
        self._old_memory = self.prepare_memory(message)
        synopsis = ResolveConflictData(old_memory=self._old_memory, new_info=message.fact)
        prompt = self.get_prompt(message.tenant_id, PromptType.RESOLVE_CONFLICT.value, synopsis.to_dict())
        logger.info(prompt_log(task_name=PromptType.RESOLVE_CONFLICT.value, tenant_id=message.tenant_id,
                               account_id=message.account_id, contact_id=message.contact_id, prompt=prompt))

        conflict_result: Optional[CreateResult] = None
        try:
            conflict_result: CreateResult = await self.create(self._model_client, prompt, ctx)
            logger.debug(
                f'[PROMPT_RESULT][RESOLVE_CONFLICT] resolve conflict result content: {conflict_result.content}, '
                f'tenant_id={message.tenant_id}, account_id={message.account_id}, contact_id={message.contact_id}')
        except Exception as e:
            logger.error(f'resolve conflict error: {e}, tenant_id={message.tenant_id}, '
                         f'account_id={message.account_id}, contact_id={message.contact_id}')
            logger.debug(f'resolve conflict error stack: {traceback.format_exc()}')

        await self._get_conflict_result(message, conflict_result)

    def prepare_memory(self, message: AddMemoryAgent):
        old_memory_list = []
        for old_memory in message.old_memory:
            old_memory_list.append({
                "id": old_memory.get("id"),
                "theme": old_memory.get("theme"),
                "fact": old_memory.get("fact"),
                "time": old_memory.get("occur_time"),
            })
        return old_memory_list

    async def _get_conflict_result(self, message: AddMemoryAgent, conflict_result: CreateResult) -> None:
        upsert_memory_list = []
        delete_memory_list = []
        old_memory_info = {}
        for old_memory in message.old_memory:
            old_memory_info[old_memory.get("id")] = old_memory

        try:
            new_memory = conflict_result.content if conflict_result else '{}'
            new_memory_dict = json.loads(repair_json(new_memory, ensure_ascii=False))
            message.new_memory = new_memory_dict.get("result", [])

            for resp in message.new_memory:
                logger.debug(f'new memory: {resp}')
                memory_id = resp.get("id")
                action = resp.get("action", ActionType.ADD.value)
                if action == ActionType.ADD.value or action == ActionType.UPDATE.value:
                    memory_info = self._get_memory_info(message=message, new_memory_info=resp,
                                                        old_memory_info=old_memory_info,
                                                        memory_id=memory_id, action=action)
                    if not memory_info:
                        continue
                    if action == ActionType.UPDATE.value:
                        delete_memory_list.append(memory_id)
                    upsert_memory_list.append(memory_info)
                elif action == ActionType.DELETE.value:
                    delete_memory_list.append(memory_id)
                else:
                    logger.debug(f'no action: {action}, memory id: {memory_id}')

            if delete_memory_list:
                logger.debug(f'delete memory: {delete_memory_list}')
                await self._milvus_client.delete(tenant_id=message.tenant_id, ids=delete_memory_list,
                                                 suffix=message.type)

            if upsert_memory_list:
                logger.debug(f'upsert memory: {upsert_memory_list}')
                memory_ids = await self._milvus_client.insert(tenant_id=message.tenant_id, data=upsert_memory_list,
                                                              suffix=message.type)
                if len(memory_ids) != len(upsert_memory_list):
                    logger.debug(f'upsert memory error: {memory_ids}')
                else:
                    for index, memory in enumerate(upsert_memory_list):
                        memory["id"] = memory_ids[index]

        except Exception as e:
            logger.error(f'save new memory error: {e}')
            logger.debug(f'save new memory error stack: {traceback.format_exc()}')
        finally:
            new_memory_result = []
            for memory in upsert_memory_list:
                new_memory_result.append(
                    {"id": memory.get("id"), "category": "", "theme": memory.get("theme"),
                     "fact": memory.get("fact"), "occur_time": memory.get("occur_time")})
            if test_param.test_enable:
                export_result = message.__dict__
                export_result["old_memory"] = self._old_memory
                self._excel_util.export_result(result=export_result, sheet_name="add_memory")
            await self.publish_message(AddMemoryResult(memory=new_memory_result), DefaultTopicId())

    def _get_memory_info(self, message, new_memory_info, old_memory_info, memory_id, action) -> None | Dict:
        theme = new_memory_info.get("theme")
        fact = new_memory_info.get("fact") if isinstance(new_memory_info.get("fact"), list) else list(
            new_memory_info.get("fact"))
        try:
            theme_vector = self._embedding_client.get_embeddings([new_memory_info.get("theme")])[0]
            fact_str = ""
            for item in fact:
                fact_str += str(item) + ';'
            fact_vector = self._embedding_client.get_embeddings([fact_str])[0]
        except Exception as e:
            logger.error(f'get embedding theme or fact to save memory error: {e}')
            logger.debug(f'get embedding theme or fact to save memory error stack: {traceback.format_exc()}')
            return None

        occur_time, expired_time = self._get_expired_time(new_memory_info)
        history = old_memory_info.get(memory_id).get("history") if memory_id in old_memory_info else []
        history.append(str({"action": action, "theme": theme, "fact": fact}))

        memory_info = MemorySchemaData(
            tenant_id=message.tenant_id,
            account_id=message.account_id,
            contact_id=message.contact_id,
            category="",
            theme=theme,
            fact=fact,
            history=history,
            occur_time=occur_time,
            expire_time=expired_time,
            update_time=int(time.time()),
            theme_vector=theme_vector,
            fact_vector=fact_vector
        ).to_dict()

        return memory_info

    def _get_expired_time(self, new_memory_info):
        occur_time = new_memory_info.get("time") if new_memory_info.get("time") is not None else 0
        expired_time = 0
        if new_memory_info.get("theme") is None or occur_time == 0:
            return occur_time, expired_time
        expired_field = schedule_param.delete_expired_memory_param
        for key, value in expired_field.items():
            if key not in new_memory_info.get("theme"):
                continue
            expired_time = occur_time + value * 24 * 60 * 60
        return occur_time, expired_time
