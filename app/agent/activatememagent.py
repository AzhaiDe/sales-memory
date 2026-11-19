#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
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
from app.schemas.prompt_data import ResourceConfig
from app.tool.good import search_goods
from app.tool.tool import tools
from app.tool.ybx_contact_info import get_contact_info_ybx
from app.utils.common_utils import get_memory_type, timestamp_to_datetime


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


def _load_tenant_config(tenant_id: str) -> tuple[UserPromptConfig, ResourceConfig | None]:
    try:
        session = MariaDBClient.get_instance().session
        row = session.query(ActivateMemoryEntity).filter(ActivateMemoryEntity.tenant_id == tenant_id).first()
        if row is None:
            return UserPromptConfig(), None
        prompt_raw = json.loads(row.prompt_config or "{}")
        resource_raw = json.loads(row.resource_config or "{}")
        known = {key: prompt_raw[key] for key in UserPromptConfig.__dataclass_fields__ if key in prompt_raw}
        prompt_cfg = UserPromptConfig.to_class(known) if known else UserPromptConfig()
        resource_cfg = ResourceConfig.to_class(resource_raw) if resource_raw.get("knowledge") else None
        return prompt_cfg, resource_cfg
    except Exception as exc:
        logger.warning(f"activate config unavailable, tenant_id={tenant_id}, use defaults: {exc}")
        try:
            MariaDBClient.get_instance().session.rollback()
        except Exception:
            pass
        return UserPromptConfig(), None


async def _load_business(request_body: AddMemoryRequest) -> dict:
    empty = {"order_info": "", "good_info": "", "customer_info": "", "child_info": ""}
    try:
        info = await tools["get_info_ybx"](request_body.contact_id, tenant_id=request_body.tenant_id)
        contact = await get_contact_info_ybx(request_body.contact_id, tenant_id=request_body.tenant_id)
        return {
            "order_info": info.get("order_info", ""),
            "good_info": info.get("good_info", ""),
            "child_info": info.get("child_info", ""),
            "customer_info": json.dumps(contact, ensure_ascii=False),
        }
    except Exception as exc:
        logger.warning(
            f"business data unavailable, tenant_id={request_body.tenant_id}, "
            f"contact_id={request_body.contact_id}, continue with chat only: {exc}"
        )
        return empty


async def _build_synopsis(request_body: AddMemoryRequest, prompt_config: UserPromptConfig,
                          resource_config: ResourceConfig | None) -> dict:
    contact_id: str = request_body.contact_id
    chat_history: list[str] = list()
    for context in request_body.contexts:
        role = "销售" if context.role == SenderType.SALESMAN.value else "客户"
        when = timestamp_to_datetime(context.msgTime) if context.msgTime else ""
        chat_history.append(f"[{role}][{when}]：{context.content}")
    if len(chat_history) > prompt_config.chat_history_max_turns:
        chat_history = chat_history[-prompt_config.chat_history_max_turns:]
    business = await _load_business(request_body)
    logger.info(
        f"activate synopsis ready, tenant_id={request_body.tenant_id}, contact_id={contact_id}, "
        f"messages={len(chat_history)}, resource={'yes' if resource_config else 'no'}"
    )
    return {
        "chat_history": chat_history,
        "order_info": business["order_info"],
        "good_info": business["good_info"],
        "customer_info": business["customer_info"],
        "current_day": datetime.now().strftime("%Y-%m-%d"),
        "child_info": business["child_info"],
    }


def _normalize_portrait(portrait: dict) -> dict:
    normalized = {}
    for category, entry in portrait.items():
        if isinstance(entry, dict) and entry:
            normalized[str(category)] = entry
        elif entry not in (None, "", [], {}):
            normalized[str(category)] = {"内容": entry}
    return normalized


def _safe_tool(fn):
    @wraps(fn)
    async def wrapped(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            logger.warning(f"tool {fn.__name__} failed: {exc}")
            return {"error": "工具暂时不可用"}
    return wrapped


def _portrait_from_messages(message: AddMemoryRequest, messages) -> dict:
    portrait = {}
    for item in messages:
        content = getattr(item, "content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        parsed = repair_json(message, content)
        if not isinstance(parsed, dict):
            continue
        parsed = _normalize_portrait(parsed)
        if parsed:
            portrait = parsed
    return portrait


@type_subscription(topic_type=TopicType.ACTIVATE_MEM_AGENT.value)
class ActivateMemAgent(BaseAgent):
    """根据聊天和业务资料生成客户画像，再交给 ActivateMemStore。"""

    def __init__(self):
        super().__init__("用于生成客户激活画像的agent")
        config = PrivateGPTConfig(
            model_name=qwq32b_gpt_params.model_name,
            api_base=qwq32b_gpt_params.api_base,
            api_key=qwq32b_gpt_params.api_key,
        )
        self._model_client = ModelClientFactory.get_client(config)
        self._prompt_manager = None

    def _prompts(self, tenant_id: str) -> PromptManager:
        if self._prompt_manager is None:
            self._prompt_manager = PromptManager(tenant_id)
        return self._prompt_manager

    @message_handler
    @BaseAgent.handle_exceptions
    @BaseAgent.trace_performance
    async def handle_add_memory(self, message: AddMemoryRequest, ctx: MessageContext) -> None:
        prompt_config, resource_config = _load_tenant_config(message.tenant_id)
        synopsis = await _build_synopsis(message, prompt_config, resource_config)
        manager = self._prompts(message.tenant_id)
        primary_prompt = manager.load_prompt("activate_mem_primary")
        critic_prompt = manager.load_prompt("activate_mem_critic")
        user_prompt = manager.load_prompt("activate_mem_user", synopsis)
        if not primary_prompt or not critic_prompt or not user_prompt:
            raise AgentInitializationException(message="Activation prompts are empty")

        primary = AssistantAgent(
            AgentRole.PRIMARY.value,
            model_client=self._model_client,
            tools=[_safe_tool(fn) for fn in (*tools.values(), search_goods)],
            system_message=primary_prompt,
        )
        critic = AssistantAgent(
            AgentRole.CRITIC.value,
            model_client=self._model_client,
            system_message=critic_prompt,
        )
        team = RoundRobinGroupChat(
            [primary, critic],
            termination_condition=TextMentionTermination("PASS"),
            max_turns=prompt_config.group_chat_max_turns,
        )
        task_result: TaskResult = await team.run(task=user_prompt, cancellation_token=ctx.cancellation_token)
        portrait = _portrait_from_messages(message, task_result.messages)
        if not portrait:
            raise AgentMemoryException(message="Activation produced an empty profile")

        body = AddMemoryAgent(
            tenant_id=message.tenant_id,
            contact_id=message.contact_id,
            account_id=message.account_id,
            type=get_memory_type(message.type),
            contexts=list(message.contexts),
            context=json.dumps(portrait, ensure_ascii=False),
        )
        await self.publish_message(
            body, topic_id=TopicId(TopicType.ACTIVATE_MEM_STORE.value, source=self.id.key)
        )
