from typing import Optional
from redis import Redis, ConnectionPool
from app.config.setting import redis_param
from app.clients.base import BaseClient


class RedisClient(BaseClient):
    _instance: Optional['RedisClient'] = None

    def __init__(self):
        super().__init__()
        self._pool: Optional[ConnectionPool] = None

    @classmethod
    def get_instance(cls) -> 'RedisClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self) -> None:
        if not self._pool:
            self._pool = ConnectionPool(
                host=redis_param.redis_host, port=redis_param.redis_port, db=redis_param.redis_db,
                username=redis_param.redis_username, password=redis_param.redis_passwd,
                decode_responses=True, max_connections=50, socket_timeout=5, socket_connect_timeout=5
            )
            self._client = Redis(connection_pool=self._pool)

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
        if self._pool:
            self._pool.disconnect()
            self._pool = None

    def is_connected(self) -> bool:
        return self._client is not None and self._pool is not None

    @property
    def redis(self) -> Redis:
        return self.client
