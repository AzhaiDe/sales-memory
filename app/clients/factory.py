import asyncio

from redis import Redis
from sqlalchemy.orm import Session

from app.clients.mariadb import MariaDBClient
from app.clients.milvus import AsyncMilvusClient
from app.clients.rag import RagClient
from app.clients.redis import RedisClient


class ClientFactory:
    @classmethod
    def get_mariadb_client(cls) -> Session:
        return MariaDBClient.get_instance().session

    @classmethod
    def get_redis_client(cls) -> Redis:
        return RedisClient.get_instance().redis

    @classmethod
    async def get_milvus_client(cls):
        return await AsyncMilvusClient.get_instance().milvus

    @classmethod
    def get_rag_client(cls):
        return RagClient.get_instance().rag

    @classmethod
    async def close_all(cls) -> None:
        MariaDBClient.get_instance().close()
        RedisClient.get_instance().close()
        await AsyncMilvusClient.get_instance().close()
        RagClient.get_instance().close()
