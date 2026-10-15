#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
import time

from autogen_core import SingleThreadedAgentRuntime, TopicId, ClosureContext, ClosureAgent, DefaultSubscription, MessageContext

from app.config.logger_setup import logger
from app.agent.extractfact import ExtractFactAgent
from app.agent.resolveconflict import ResolveConflictAgent
from app.agent.retrievememory import RetrieveMemoryAgent
from app.enums.agent_topic import TopicType
from app.grpc.proto.internal.salesmemory_pb2 import AddMemoryRequest, SearchMemoryRequest
from app.schemas.body import AddMemoryResult, SearchMemoryResult


async def add_memory_flow(request_body: AddMemoryRequest) -> AddMemoryResult:
    start_time = time.time()
    queue = asyncio.Queue[AddMemoryResult]()

    async def output_result(_agent: ClosureContext, message: AddMemoryResult, ctx: MessageContext) -> None:
        await queue.put(message)

    runtime = SingleThreadedAgentRuntime()
    await ExtractFactAgent.register(runtime, type=TopicType.EXTRACT_FACT_AGENT.value, factory=lambda: ExtractFactAgent())
    await RetrieveMemoryAgent.register(runtime, type=TopicType.RETRIEVE_MEMORY_AGENT.value, factory=lambda: RetrieveMemoryAgent())
    await ResolveConflictAgent.register(runtime, type=TopicType.RESOLVE_CONFLICT_AGENT.value, factory=lambda: ResolveConflictAgent())
    await ClosureAgent.register_closure(runtime, type=TopicType.CLOSURE_AGENT.value, closure=output_result,
                                        subscriptions=lambda: [DefaultSubscription()])
    runtime.start()
    await runtime.publish_message(message=request_body,
                                  topic_id=TopicId(type=TopicType.EXTRACT_FACT_AGENT.value, source="default"))
    await runtime.stop_when_idle()
    res = await queue.get()
    end_time = time.time()
    logger.info(f"[PERF_METRICS][ONLINE] flow=add_memory_flow "
                f"tenant_id={request_body.tenant_id} account_id={request_body.account_id}"
                f"contact_id={request_body.contact_id} duration={end_time - start_time:.2f}s")
    return res


async def search_memory_flow(request_body: SearchMemoryRequest) -> SearchMemoryResult:
    start_time = time.time()
    queue = asyncio.Queue[SearchMemoryResult]()

    async def output_result(_agent: ClosureContext, message: SearchMemoryResult, ctx: MessageContext) -> None:
        await queue.put(message)

    runtime = SingleThreadedAgentRuntime()
    await RetrieveMemoryAgent.register(runtime, type=TopicType.RETRIEVE_MEMORY_AGENT.value, factory=lambda: RetrieveMemoryAgent())
    await ClosureAgent.register_closure(runtime, type=TopicType.CLOSURE_AGENT.value, closure=output_result,
                                        subscriptions=lambda: [DefaultSubscription()])
    runtime.start()
    await runtime.publish_message(message=request_body,
                                  topic_id=TopicId(type=TopicType.RETRIEVE_MEMORY_AGENT.value, source="default"))
    await runtime.stop_when_idle()
    res = await queue.get()
    end_time = time.time()
    logger.info(f"[PERF_METRICS][ONLINE] flow=search_memory_flow "
                f"tenant_id={request_body.tenant_id} account_id={request_body.account_id}"
                f"contact_id={request_body.contact_id} duration={end_time - start_time:.2f}s")
    return res
