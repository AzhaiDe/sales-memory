#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
import time

from autogen_core import SingleThreadedAgentRuntime, ClosureContext, MessageContext, ClosureAgent, DefaultSubscription, TopicId

from app.agent.activatememagent import ActivateMemAgent
from app.agent.activatememstore import ActivateMemStore
from app.config.logger_setup import logger
from app.enums.agent_topic import TopicType
from app.grpc.proto.internal.salesmemory_pb2 import AddMemoryRequest, SearchMemoryRequest
from app.schemas.body import AddMemoryResult, SearchMemoryResult


async def add_memory_flow(request_body: AddMemoryRequest) -> AddMemoryResult:
    start_time = time.time()
    queue = asyncio.Queue[AddMemoryResult]()

    async def output_result(_agent: ClosureContext, message: AddMemoryResult, ctx: MessageContext) -> None:
        await queue.put(message)

    runtime = SingleThreadedAgentRuntime()
    await ActivateMemAgent.register(runtime, type=TopicType.ACTIVATE_MEM_AGENT.value, factory=lambda: ActivateMemAgent())
    await ActivateMemStore.register(runtime, type=TopicType.ACTIVATE_MEM_STORE.value, factory=lambda: ActivateMemStore())
    await ClosureAgent.register_closure(runtime, type=TopicType.CLOSURE_AGENT.value, closure=output_result,
                                        subscriptions=lambda: [DefaultSubscription()])
    runtime.start()
    await runtime.publish_message(message=request_body,
                                  topic_id=TopicId(type=TopicType.ACTIVATE_MEM_AGENT.value, source="default"))
    await runtime.stop_when_idle()
    res = await queue.get()
    end_time = time.time()
    logger.info(f"[PERF_METRICS][ACTIVATE] flow=add_memory_flow "
                f"tenant_id={request_body.tenant_id} account_id={request_body.account_id} "
                f"contact_id={request_body.contact_id} duration={end_time - start_time:.2f}s")
    return res


async def search_memory_flow(request_body: SearchMemoryRequest) -> SearchMemoryResult:
    start_time = time.time()
    queue = asyncio.Queue[SearchMemoryResult]()

    async def output_result(_agent: ClosureContext, message: SearchMemoryResult, ctx: MessageContext) -> None:
        await queue.put(message)

    runtime = SingleThreadedAgentRuntime()
    await ActivateMemStore.register(runtime, type=TopicType.ACTIVATE_MEM_STORE.value, factory=lambda: ActivateMemStore())
    await ClosureAgent.register_closure(runtime, type=TopicType.CLOSURE_AGENT.value, closure=output_result,
                                        subscriptions=lambda: [DefaultSubscription()])
    runtime.start()
    await runtime.publish_message(message=request_body,
                                  topic_id=TopicId(type=TopicType.ACTIVATE_MEM_STORE.value, source="default"))
    await runtime.stop_when_idle()
    res = await queue.get()
    end_time = time.time()
    logger.info(f"[PERF_METRICS][ACTIVATE] flow=search_memory_flow "
                f"tenant_id={request_body.tenant_id} account_id={request_body.account_id} "
                f"contact_id={request_body.contact_id} duration={end_time - start_time:.2f}s")
    return res
