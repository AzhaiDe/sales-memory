#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import List
from google.protobuf.internal import containers as _containers
from app.enums.sender_types import SenderType
from app.utils.common_utils import timestamp_to_datetime
from app.config.logger_setup import logger
from app.grpc.proto.internal.salesmemory_pb2 import Context


class ContextUtil:
    def __init__(self, context: _containers.RepeatedCompositeFieldContainer):
        self._context = context
        self._context_list: List = []
        self._process_context()

    def _process_context(self):
        contexts_list: List = []
        for ctx in self._context:
            role: str = ctx.role
            content: str = ctx.content.replace("\r", "\n")
            msg_time: int = timestamp_to_datetime(ctx.msgTime)
            if role == SenderType.CUSTOMER.value:
                contexts_list.append(f'[{SenderType.CUSTOMER.get_value()}][{msg_time}]：{content}')
            elif role == SenderType.SALESMAN.value:
                contexts_list.append(f'[{SenderType.SALESMAN.get_value()}][{msg_time}]：{content}')
            else:
                logger.error(f"unknown role: {role}")
        self._context_list = contexts_list
        return "\n".join(contexts_list)

    def get_latest_customer_msg_with_timestamp(self) -> str:
        latest_context = next(
            (context for context in self._context if context.role == SenderType.CUSTOMER.value), None
        )
        latest_msg = ""
        if latest_context:
            msg_time = timestamp_to_datetime(latest_context.msgTime)
            content = latest_context.content.replace("\r", "\n")
            latest_msg = f'[{SenderType.CUSTOMER.get_value()}][{msg_time}]：{content}'
        return latest_msg

    def get_context_with_timestamp(self):
        reverse_context_list = list(reversed(self._context_list))
        return "\n".join(reverse_context_list)
