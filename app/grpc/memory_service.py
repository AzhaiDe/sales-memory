#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import logging
import asyncio
import time

from app.config.logger_setup import logger
from app.enums.mem_types import MemType
from app.exceptions.error_codes import ErrorCode
from app.flow.activatememoryflow import add_memory_flow as activate_add_memory_flow
from app.flow.activatememoryflow import search_memory_flow as activate_search_memory_flow
from app.flow.onlinememoryflow import add_memory_flow as online_add_memory_flow
from app.flow.onlinememoryflow import search_memory_flow as online_search_memory_flow
from app.grpc.proto.internal.salesmemory_pb2 import AddMemoryRequest, AddMemoryResponse, SearchMemoryRequest, \
    AddMemoryRequests, AddMemoryResponses
from app.grpc.proto.internal.salesmemory_pb2_grpc import MemoryServiceServicer
from app.schemas.body import AddMemoryResult, SearchMemoryResult


class MemoryService(MemoryServiceServicer):
    async def AddMemories(self, requests: AddMemoryRequests, context):
        logger.info(f'receive multi request, len(requests)={requests.requests}')
        start_time = time.time()
        tasks = [self.AddMemory(request, context) for request in requests.requests]
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        logger.info(f'multi request have done, len(response)={responses}, cost={int(end_time - start_time)}s')
        return AddMemoryResponses(response=responses)

    async def AddMemory(self, request: AddMemoryRequest, context):
        logger.info(f'receive a request, tenant_id={request.tenant_id}, account_id={request.account_id}, '
                    f'contact_id={request.contact_id}, type is {request.type}')
        try:
            if MemType.ACTIVATE == request.type:
                res: AddMemoryResult = await activate_add_memory_flow(request)
            else:
                res: AddMemoryResult = await online_add_memory_flow(request)
            logging.debug(res)
            if res.error_msg:
                context.set_code(res.status_code)
                context.set_details(res.error_msg)
                logger.error(f'request have done, tenant_id={request.tenant_id}, error={str(res.error_msg)}')
                return AddMemoryResponse()
            response = AddMemoryResponse(memory=res.memory)
            logger.info(f'request have done, tenant_id={request.tenant_id}, contact_id={request.contact_id}')
            return response
        except Exception as e:
            context.set_code(ErrorCode.UNKNOWN_ERROR.code)
            context.set_details(str(e))
            logger.error(f'request failed, tenant_id={request.tenant_id}, error={str(e)}')
            return AddMemoryResponse()

    async def SearchMemory(self, request: SearchMemoryRequest, context):
        logger.info(f'receive a request, tenant_id={request.tenant_id}, account_id={request.account_id}, '
                    f'contact_id={request.contact_id}, type is {request.type}')
        try:
            if MemType.ACTIVATE == request.type:
                res: SearchMemoryResult = await activate_search_memory_flow(request)
            else:
                res: SearchMemoryResult = await online_search_memory_flow(request)
            logging.debug(res)
            if res.error_msg:
                context.set_code(res.status_code)
                context.set_details(res.error_msg)
                logger.error(f'request have done, tenant_id={request.tenant_id}, error={str(res.error_msg)}')
                return AddMemoryResponse()
            response = AddMemoryResponse(memory=res.memory)
            logger.info(f'request have done, tenant_id={request.tenant_id}, contact_id={request.contact_id}')
            return response
        except Exception as e:
            context.set_code(ErrorCode.UNKNOWN_ERROR.code)
            context.set_details(str(e))
            logger.error(f'request failed, tenant_id={request.tenant_id}, error={str(e)}')
            return AddMemoryResponse()
