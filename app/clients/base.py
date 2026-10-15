import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Optional, Callable, TypeVar, cast

from app.config.logger_setup import logger

T = TypeVar('T')


class BaseClient(ABC):
    """数据库客户端基类，定义统一接口"""

    _instance: Optional[Any] = None

    def __init__(self):
        self._client = None

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @property
    def client(self) -> Any:
        if not self.is_connected():
            self.connect()
        return self._client

    @staticmethod
    def trace_performance(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                result = await func(self, *args, **kwargs)
                end_time = time.time()
                elapsed = end_time - start_time
                logger.debug(f"[PERF_METRICS][CLIENT_DURATION] "
                             f"{func.__name__} 耗时: {elapsed:.3f}s "
                             f"tenant_id={kwargs.get('tenant_id', '')} "
                             f"account_id={kwargs.get('account_id', '')} "
                             f"contact_id={kwargs.get('contact_id', '')} "
                             f"duration={end_time - start_time:.2f}s")
                return result
            except Exception as e:
                end_time = time.time()
                logger.error(f"[PERF_METRICS][CLIENT_DURATION] "
                             f"{func.__name__} 失败: 耗时={end_time - start_time:.3f}s, 错误={str(e)}")
                raise
        return cast(Callable[..., T], wrapper)
