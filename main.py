#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import asyncio
import grpc
import grpc.aio

from app.config.logger_setup import logger
from app.config.setting import server_param, consul_param, schedule_param
from app.grpc.memory_service import MemoryService
from app.grpc.proto.internal import salesmemory_pb2_grpc
from app.clients.factory import ClientFactory
from app.scheduler.scheduler import MemoryScheduler


async def serve():
    server = grpc.aio.server()
    salesmemory_pb2_grpc.add_MemoryServiceServicer_to_server(MemoryService(), server)
    listen_addr = f"{server_param.host}:{server_param.port}"
    server.add_insecure_port(listen_addr)
    logger.info(f"Sales Memory gRPC server starting on {listen_addr}")
    await server.start()

    if schedule_param.schedule_enable:
        scheduler = MemoryScheduler()
        scheduler.start()

    try:
        await server.wait_for_termination()
    finally:
        await ClientFactory.close_all()


if __name__ == "__main__":
    asyncio.run(serve())
