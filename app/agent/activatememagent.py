#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import TopicId, type_subscription, message_handler, MessageContext
from json_repair import json_repair

from app.agent.base import BaseAgent
from app.clients.mariadb import MariaDBClient
from app.config.logger_setup import logger
from app.config.setting import qwq32b_gpt_params
from app.enums.agent_topic import TopicType
from app.enums.sender_types import SenderType
from app.exceptions.custom import AgentInitializationException, AgentMemoryException
from app.grpc.proto.internal.salesmemory_pb2 import AddMemoryRequest
from app.models.factory import ModelClientFactory
from app.models.model_config import PrivateGPTConfig
from app.models.prompt_manager import PromptManager
from app.schemas.body import AddMemoryAgent
from app.schemas.db_schema import ActivateMemoryEntity
from app.schemas.prompt_data import PromptConfig, ResourceConfig
from app.tool.tool import tools
from app.utils.chunk_utils import chunk_chat_history
from app.utils.common_utils import get_memory_type
from app.utils.token_utils import system_tokens, user_tokens


class AgentRole(Enum):
    PRIMARY = "primary"
    CRITIC = "critic"


@dataclass
class UserPromptConfig(object):
    group_chat_max_turns: int = 5
    chat_history_max_turns: int = 20
    order_history_max_counts: int = 20

    @classmethod
    def to_class(cls, content: dict) -> 'UserPromptConfig':
        return UserPromptConfig(**content)


def repair_json(message: AddMemoryRequest, content: str) -> dict:
    def _extract_values(parent, data, types):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    tmp = _extract_values(data, value, types)
                    if isinstance(tmp, str):
                        data[key] = tmp
                elif key == types:
                    parent = value
        return parent

    logger.debug(
        f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
        f"contact_id={message.contact_id}, llm final content={content}"
    )

    if len(content) == 0:
        return dict()

    json_content = json_repair.loads(content)
    logger.debug(
        f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
        f"contact_id={message.contact_id}, json repair content={json.dumps(json_content, ensure_ascii=False)}"
    )

    if isinstance(json_content, list):
        # 可能模型返回了多个 json，这里取最后一个非空 dict，尝试着拯救一下
        tmp = {}
        for item in json_content:
            if isinstance(item, dict) and len(item) != 0:
                tmp = item
        json_content = tmp

    if not isinstance(json_content, dict):
        logger.error(
            f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
            f"contact_id={message.contact_id}, build milvus body failed, content not a dict"
        )
        return dict()

    json_content = _extract_values(json_content, json_content, "value")
    logger.debug(
        f"tenant_id={message.tenant_id}, account_id={message.account_id}, "
        f"contact_id={message.contact_id}, json extract content={json.dumps(json_content, ensure_ascii=False)}"
    )

    return json_content


async def _build_synopsis(request_body: AddMemoryRequest, prompt_config: UserPromptConfig,
                          resource_config: ResourceConfig) -> dict:
    contact_id: str = request_body.contact_id

    chat_history: list[str] = list()
    for context in request_body.contexts:
        role = "销售" if context.role == SenderType.SALESMAN.value else "客户"
