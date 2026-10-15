#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import traceback
from datetime import datetime
from typing import Optional

from autogen_core import type_subscription, message_handler, MessageContext, TopicId, DefaultTopicId
from autogen_core.models import CreateResult
from json_repair import repair_json

from app.agent.base import BaseAgent
from app.config.logger_setup import logger
from app.config.setting import qwq32b_gpt_params
from app.enums.agent_topic import TopicType
from app.enums.prompt_types import PromptType
from app.exceptions.custom import ModelResponseParseException
from app.grpc.proto.internal.salesmemory_pb2 import AddMemoryRequest
from app.models.factory import ModelClientFactory
from app.models.model_config import PrivateGPTConfig
from app.schemas.body import AddMemoryAgent, AddMemoryResult
from app.schemas.prompt_data import ExtractFactData
from app.utils.common_utils import prompt_log, get_memory_type
from app.utils.context_utils import ContextUtil


@type_subscription(topic_type=TopicType.EXTRACT_FACT_AGENT.value)
class ExtractFactAgent(BaseAgent):
    """Extract Fact Agent，提取记忆体事实"""

    def __init__(self):
        super().__init__("用于提取记忆体事实的agent")
        qwq32b_config = PrivateGPTConfig(model_name=qwq32b_gpt_params.model_name,
                                         api_base=qwq32b_gpt_params.api_base,
                                         api_key=qwq32b_gpt_params.api_key)
        self._model_client = ModelClientFactory.get_client(qwq32b_config)
        self._fact_result: Optional[AddMemoryAgent] = None

    @message_handler
    @BaseAgent.handle_exceptions
    @BaseAgent.trace_performance
    async def handle_add_memory(self, message: AddMemoryRequest, ctx: MessageContext) -> None:
        ctx_utils = ContextUtil(message.contexts)
        context = ctx_utils.get_context_with_timestamp()
        memory_type = get_memory_type(message.type)

        self._fact_result = AddMemoryAgent(
            tenant_id=message.tenant_id,
            contact_id=message.contact_id,
            account_id=message.account_id,
            type=memory_type,
            contexts=message.contexts,
            context=context
        )

        synopsis = ExtractFactData(context=context)
        prompt = self.get_prompt(message.tenant_id, PromptType.EXTRACT_FACT.value, synopsis.to_dict())

        fact_result: Optional[CreateResult] = None
        try:
            fact_result: CreateResult = await self.create(self._model_client, prompt, ctx)
            logger.info(f'[PROMPT_RESULT][EXTRACT_FACT] extract fact result content: {fact_result.content}, '
                        f'tenant_id={self._fact_result.tenant_id}, '
                        f'account_id={self._fact_result.account_id}, '
                        f'contact_id={self._fact_result.contact_id}')
        except Exception as e:
            logger.error(f'quit scene error: {e}, '
                         f'tenant_id={self._fact_result.tenant_id}, '
                         f'account_id={self._fact_result.account_id}, '
                         f'contact_id={self._fact_result.contact_id}')
            logger.debug(f'extract fact error stack: {traceback.format_exc()}')

        output = fact_result.content if fact_result else '{}'
        logger.debug(prompt_log(task_name=PromptType.EXTRACT_FACT.value, tenant_id=message.tenant_id,
                                account_id=message.account_id, contact_id=message.contact_id, prompt=prompt,
                                output=output))
        await self._get_fact_result(fact_result)

    async def _get_fact_result(self, fact_result: CreateResult):
        try:
            content = fact_result.content if fact_result else '{}'
            content_dict = json.loads(repair_json(content, ensure_ascii=False))
            self._fact_result.fact = content_dict.get("result", {}) if isinstance(content_dict, dict) else {}
            for item in self._fact_result.fact:
                if item.get("time", None) is not None:
                    item["time"] = int(datetime.strptime(item["time"], "%Y-%m-%d").timestamp())
                else:
                    item["time"] = int(datetime.now().timestamp())
        except Exception as e:
            logger.error(f'get fact result error: {e}')
            logger.debug(f'get fact result error stack: {traceback.format_exc()}')
            raise ModelResponseParseException()
        finally:
            if not self._fact_result.fact:
                await self.publish_message(AddMemoryResult(), DefaultTopicId())
            else:
                await self.publish_message(
                    self._fact_result,
                    topic_id=TopicId(TopicType.RETRIEVE_MEMORY_AGENT.value, source=self.id.key)
                )
